"""Temporal definitions contain orchestration only; business semantics live in activities."""

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy


@workflow.defn(name="cca-coordination")
class CoordinationWorkflow:
    def __init__(self):
        self.messages: list[dict] = []
        self.seen: set[str] = set()
        self.status = "QUEUED"

    @workflow.signal(name="decision")
    def decision(self, envelope: dict) -> None:
        identity = str(envelope.get("id", ""))
        if identity and identity not in self.seen:
            self.seen.add(identity)
            self.messages.append(envelope)

    @workflow.query(name="status")
    def current_status(self) -> str:
        return self.status

    @workflow.run
    async def run(self, run_id: str, generation: int = 0) -> str:
        retry = RetryPolicy(initial_interval=timedelta(seconds=1), maximum_attempts=3)
        self.status = await workflow.execute_activity(
            "cca-analyze",
            args=[run_id, generation] if generation else [run_id],
            start_to_close_timeout=timedelta(minutes=3),
            retry_policy=retry,
        )
        while self.status == "WAITING_APPROVAL":
            try:
                await workflow.wait_condition(
                    lambda: bool(self.messages), timeout=timedelta(days=30)
                )
            except TimeoutError:
                self.status = await workflow.execute_activity(
                    "cca-expire",
                    args=[run_id, generation] if generation else [run_id],
                    start_to_close_timeout=timedelta(seconds=30),
                    retry_policy=retry,
                )
                break
            envelope = self.messages.pop(0)
            self.status = await workflow.execute_activity(
                "cca-advance",
                args=[run_id, envelope["payload"], generation]
                if generation
                else [run_id, envelope["payload"]],
                start_to_close_timeout=timedelta(minutes=3),
                retry_policy=retry,
            )
        return self.status
