"""Explicit NON-DURABLE execution harness, not a deployment/runtime replacement.

Used only by offline tests or --diagnostic-runtime on dependency-restricted hosts.
It owns no scheduler, queue, retry system or workflow engine.
"""

from app.ports.services import WorkflowDriver


class DiagnosticRuntime:
    name = "diagnostic-NON-DURABLE"

    def __init__(self, coordinator: WorkflowDriver) -> None:
        self.coordinator = coordinator

    def start(self, run_id: str) -> str:
        self.coordinator.begin(run_id)
        return run_id

    def signal(self, run_id: str, message: dict, message_id: str) -> None:
        self.coordinator.advance(run_id, message)

    def status(self, run_id: str) -> str:
        return self.coordinator.status(run_id)

    def cancel(self, run_id: str, *, generation: int | None = None) -> None:
        # The caller updates the authoritative run first. There is no background worker.
        return None

    def resume(self, run_id: str) -> None:
        self.coordinator.begin(run_id)

    def close(self) -> None:
        return None
