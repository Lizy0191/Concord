from app.application.analysis import AnalysisService
from app.application.streaming import custom, emit
from app.domain.actions import AuditRecord, Principal
from app.domain.errors import Conflict
from app.domain.events import ProjectEvent
from app.domain.models import ProjectState, utcnow
from app.domain.runs import TERMINAL_STATUSES, AgentRun
from app.domain.transitions import apply_event
from app.policies.actions import require
from app.ports.coordination import RepositoryFactory


class CoordinationService:
    def __init__(
        self, factory: RepositoryFactory, analysis: AnalysisService, runtime_name: str = "dbos"
    ) -> None:
        self.factory, self.analysis, self.runtime_name = factory, analysis, runtime_name

    def seed(self, state: ProjectState, principal: Principal, reset: bool = False) -> AgentRun:
        require(principal, "reset")
        with self.factory.open(state.project.id, write=True) as repo:
            existing = next((p for p in repo.projects() if p.project.id == state.project.id), None)
            if existing and not reset:
                runs = repo.runs(state.project.id)
                if runs:
                    return runs[0]
            if existing:
                state = state.model_copy(update={"version": existing.version + 1})
                for run in repo.pending_runs(state.project.id):
                    if run.status not in TERMINAL_STATUSES:
                        repo.save_run(
                            run.model_copy(update={"status": "CANCELLED", "updated_at": utcnow()})
                        )
                        custom(repo, run.id, "cancelled", {"reason": "demo reset"})
            if reset:
                repo.clear_bim_index(state.project.id)
            repo.save_state(state)
            run = AgentRun(project_id=state.project.id, runtime=self.runtime_name)
            repo.save_run(run)
            emit(repo, run.id, "RUN_STARTED")
            repo.audit(
                AuditRecord(
                    project_id=state.project.id,
                    action="DEMO_RESET" if reset else "PROJECT_SEEDED",
                    actor=principal.id,
                    run_id=run.id,
                )
            )
            return run

    def ingest(self, event: ProjectEvent, principal: Principal) -> AgentRun:
        require(principal, "ingest")
        with self.factory.open(event.project_id, write=True) as repo:
            previous = repo.event(event.id)
            if previous:
                # A retried JSON request may omit server-defaulted observation time.
                # Preserve its original timestamp; explicitly changed timestamps still conflict.
                if "observed_at" not in event.model_fields_set:
                    event = event.model_copy(update={"observed_at": previous.observed_at})
                if previous != event:
                    raise Conflict("Event id already belongs to different content")
                return repo.run_for_event(event.id)
            state = repo.state(event.project_id)
            updated = apply_event(state, event)
            repo.save_state(updated)
            repo.save_event(event)
            run = AgentRun(
                project_id=event.project_id, event_id=event.id, runtime=self.runtime_name
            )
            repo.save_run(run)
            emit(repo, run.id, "RUN_STARTED")
            custom(
                repo,
                run.id,
                "event-ingested",
                {"event_id": event.id, "kind": event.kind, "version": updated.version},
            )
            repo.audit(
                AuditRecord(
                    project_id=event.project_id,
                    action="EVENT_INGESTED",
                    actor=principal.id,
                    run_id=run.id,
                    detail={"event_id": event.id, "kind": event.kind, "version": updated.version},
                )
            )
            return run

    def fail(
        self,
        run_id: str,
        code: str,
        message: str,
        *,
        generation: int | None = None,
        previous_analysis_id: str | None = None,
    ) -> None:
        with self.factory.open() as repo:
            run = repo.run(run_id)
        with self.factory.open(run.project_id, write=True) as repo:
            current = repo.run(run_id)
            if (
                current.status in {"CANCELLED", "EXPIRED", "COMPLETED"}
                or (generation is not None and current.generation != generation)
                or (
                    generation is not None
                    and current.status == "WAITING_APPROVAL"
                    and current.analysis_id != previous_analysis_id
                )
            ):
                return
            repo.save_run(
                current.model_copy(
                    update={
                        "status": "FAILED",
                        "error": f"{code}: {message}",
                        "updated_at": utcnow(),
                    }
                )
            )
            emit(repo, run_id, "RUN_ERROR", code=code, message=message)
            repo.audit(
                AuditRecord(
                    project_id=run.project_id,
                    action="RUN_FAILED",
                    actor="runtime",
                    run_id=run_id,
                    detail={"code": code},
                )
            )

    def cancel(self, run_id: str, principal: Principal, *, generation: int | None = None) -> str:
        require(principal, "execute")
        with self.factory.open() as repo:
            run = repo.run(run_id)
        with self.factory.open(run.project_id, write=True) as repo:
            current = repo.run(run_id)
            if generation is not None and current.generation != generation:
                raise Conflict("Run was resumed while cancellation was being requested")
            if current.status not in TERMINAL_STATUSES:
                repo.save_run(
                    current.model_copy(update={"status": "CANCELLED", "updated_at": utcnow()})
                )
                custom(repo, run_id, "cancelled", {"actor": principal.id})
                repo.audit(
                    AuditRecord(
                        project_id=run.project_id,
                        action="RUN_CANCELLED",
                        actor=principal.id,
                        run_id=run_id,
                    )
                )
                return "CANCELLED"
            return current.status

    def expire(self, run_id: str, *, generation: int | None = None) -> None:
        with self.factory.open() as repo:
            run = repo.run(run_id)
        with self.factory.open(run.project_id, write=True) as repo:
            current = repo.run(run_id)
            if generation is not None and current.generation != generation:
                return
            if current.status not in TERMINAL_STATUSES:
                repo.save_run(
                    current.model_copy(update={"status": "EXPIRED", "updated_at": utcnow()})
                )
                custom(
                    repo,
                    run_id,
                    "expired",
                    {"reason": "approval wait exceeded configured lifetime"},
                )
                repo.audit(
                    AuditRecord(
                        project_id=run.project_id,
                        action="RUN_EXPIRED",
                        actor="runtime",
                        run_id=run_id,
                    )
                )
