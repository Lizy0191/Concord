"""Run lifecycle routes and explicit composition of run/action route families."""

from fastapi import APIRouter, Depends

from app.api.actions import router as actions_router
from app.api.auth import CurrentUser, services
from app.api.run_events import router as events_router
from app.application.streaming import custom
from app.domain.actions import AuditRecord
from app.domain.errors import Conflict
from app.domain.models import utcnow
from app.domain.runs import AgentRun
from app.policies.actions import require

router = APIRouter(prefix="/api", tags=["runs-actions"])


@router.get("/runs/{run_id}", response_model=AgentRun)
def get_run(run_id: str, user: CurrentUser, svc=Depends(services)):
    require(user, "read")
    with svc.factory.open() as repo:
        return repo.run(run_id)


# Keep route order, tags, operation IDs, and public paths unchanged.
router.include_router(events_router)
router.include_router(actions_router)


@router.post("/runs/{run_id}/cancel")
def cancel(run_id: str, user: CurrentUser, svc=Depends(services)):
    require(user, "execute")
    with svc.factory.open() as repo:
        generation = repo.run(run_id).generation
    status = svc.coordination.cancel(run_id, user, generation=generation)
    if status == "CANCELLED":
        svc.runtime.cancel(run_id, generation=generation)
    return {"status": status}


@router.post("/runs/{run_id}/resume", response_model=AgentRun, status_code=202)
def resume(run_id: str, user: CurrentUser, svc=Depends(services)):
    require(user, "execute")
    with svc.factory.open() as repo:
        run = repo.run(run_id)
    with svc.factory.open(run.project_id, write=True) as repo:
        # Re-read after acquiring the project lock; a concurrent completion wins.
        run = repo.run(run_id)
        if run.status not in {"QUEUED", "FAILED", "CANCELLED", "EXPIRED"}:
            raise Conflict("Only queued/failed/cancelled/expired runs may be resumed")
        if run.status != "QUEUED":
            repo.save_run(
                run.model_copy(
                    update={
                        "status": "QUEUED",
                        "error": None,
                        "generation": run.generation + 1,
                        "updated_at": utcnow(),
                    }
                )
            )
            custom(repo, run_id, "resumed", {"generation": run.generation + 1})
            repo.audit(
                AuditRecord(
                    project_id=run.project_id,
                    action="RUN_RESUMED",
                    actor=user.id,
                    run_id=run_id,
                    detail={"generation": run.generation + 1},
                )
            )
    svc.runtime.resume(run_id)
    with svc.factory.open() as repo:
        return repo.run(run_id)
