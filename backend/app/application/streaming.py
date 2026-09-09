from app.domain.models import utcnow
from app.ports.coordination import CoordinationRepository


def emit(repo: CoordinationRepository, run_id: str, event_type: str, **fields) -> None:
    payload = {"type": event_type, "timestamp": int(utcnow().timestamp() * 1000), **fields}
    if event_type in {"RUN_STARTED", "RUN_FINISHED"}:
        payload.update(threadId=run_id, runId=run_id)
    repo.emit(run_id, payload)


def custom(repo: CoordinationRepository, run_id: str, name: str, value: dict) -> None:
    emit(repo, run_id, "CUSTOM", name=name, value=value)
