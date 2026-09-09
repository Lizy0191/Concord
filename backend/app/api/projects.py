from fastapi import APIRouter, Depends

from app.api.auth import CurrentUser, services
from app.api.schemas import WorkspaceResponse
from app.domain.events import ProjectEvent
from app.domain.models import Project
from app.domain.runs import AgentRun
from app.policies.actions import require

router = APIRouter(prefix="/api", tags=["projects"])


@router.get("/projects", response_model=list[Project])
def projects(user: CurrentUser, svc=Depends(services)):
    require(user, "read")
    with svc.factory.open() as repo:
        return [state.project for state in repo.projects()]


@router.get("/projects/{project_id}/workspace", response_model=WorkspaceResponse)
def workspace(project_id: str, user: CurrentUser, svc=Depends(services)):
    require(user, "read")
    with svc.factory.open() as repo:
        state = repo.state(project_id)
        analysis = repo.latest_analysis(project_id)
        runs = repo.runs(project_id)
        run = runs[0] if runs else None
        proposals = []
        approvals = []
        if analysis:
            proposals = [
                p for p in repo.proposals(analysis.run_id) if p.snapshot_id == analysis.snapshot.id
            ]
            approvals = [approval for p in proposals for approval in repo.approvals(p.id)]
        return WorkspaceResponse(
            state=state,
            analysis=analysis,
            run=run,
            analysis_run=repo.run(analysis.run_id) if analysis else None,
            proposals=proposals,
            approvals=approvals,
            events=repo.events(project_id),
            audit=repo.audits(project_id)[:30],
            stale=bool(
                analysis
                and (
                    analysis.snapshot.version != state.version
                    or analysis.snapshot.sources != state.sources
                )
            ),
        )


@router.post("/projects/{project_id}/events", response_model=AgentRun, status_code=202)
def ingest(project_id: str, event: ProjectEvent, user: CurrentUser, svc=Depends(services)):
    from app.domain.errors import DomainError

    if event.project_id != project_id:
        raise DomainError("Project in URL does not match event")
    run = svc.coordination.ingest(event, user)
    svc.runtime.start(run.id)
    with svc.factory.open() as repo:
        return repo.run(run.id)


@router.post("/projects/{project_id}/recheck", response_model=AgentRun, status_code=202)
def recheck(project_id: str, user: CurrentUser, svc=Depends(services)):
    require(user, "ingest")
    with svc.factory.open(project_id, write=True) as repo:
        repo.state(project_id)
        run = AgentRun(project_id=project_id, runtime=svc.runtime.name)
        repo.save_run(run)
        from app.application.streaming import emit

        emit(repo, run.id, "RUN_STARTED")
    svc.runtime.start(run.id)
    with svc.factory.open() as repo:
        return repo.run(run.id)


@router.post("/demo/reset", response_model=AgentRun, status_code=202)
def reset_demo(user: CurrentUser, svc=Depends(services)):
    from app.adapters.demo import demo_state
    from app.domain.errors import PermissionDenied

    if svc.settings.profile not in {"local", "desktop"}:
        raise PermissionDenied("Demo reset is disabled in server/full profiles")
    require(user, "reset")
    with svc.factory.open() as repo:
        active = repo.pending_runs("harbor-east")
    run = svc.coordination.seed(demo_state(), user, reset=True)
    for cancelled in active:
        svc.runtime.cancel(cancelled.id, generation=cancelled.generation)
    svc.runtime.start(run.id)
    with svc.factory.open() as repo:
        return repo.run(run.id)


@router.get("/projects/{project_id}/runs", response_model=list[AgentRun])
def project_runs(project_id: str, user: CurrentUser, svc=Depends(services)):
    require(user, "read")
    with svc.factory.open() as repo:
        repo.state(project_id)
        return repo.runs(project_id)
