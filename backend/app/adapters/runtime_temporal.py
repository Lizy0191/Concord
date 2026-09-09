"""Sync Port facade over a real Temporal client and optional embedded activity worker."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import RLock, Thread

from app.adapters.runtime_identity import bind_execution
from app.domain.errors import CapabilityUnavailable, WorkflowError
from app.domain.models import new_id
from app.ports.coordination import RepositoryFactory
from app.ports.services import WorkflowDriver


class TemporalRuntime:
    name = "temporal"

    def __init__(
        self,
        coordinator: WorkflowDriver,
        address: str,
        namespace: str,
        task_queue: str,
        *,
        factory: RepositoryFactory,
        run_worker: bool = True,
    ):
        try:
            import temporalio.client  # noqa: F401
        except ImportError as exc:
            raise CapabilityUnavailable("Install the temporal extra for TemporalRuntime") from exc
        self.coordinator, self.task_queue = coordinator, task_queue
        self.factory = factory
        self.loop = asyncio.new_event_loop()
        self.thread = Thread(target=self._serve, name="cca-temporal", daemon=True)
        self.executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="cca-activity")
        self._closed = False
        self._lifecycle_lock = RLock()
        self._worker_stopped = False
        self.worker = None
        self.worker_task = None
        self.thread.start()
        try:
            self._call(self._connect(address, namespace, run_worker), timeout=12)
        except BaseException:
            self._closed = True
            self.loop.call_soon_threadsafe(self.loop.stop)
            self.thread.join(timeout=3)
            self.executor.shutdown(wait=False, cancel_futures=True)
            raise

    def _serve(self):
        asyncio.set_event_loop(self.loop)
        try:
            self.loop.run_forever()
        finally:
            pending = asyncio.all_tasks(self.loop)
            for task in pending:
                task.cancel()
            if pending:
                self.loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            self.loop.close()

    async def _connect(self, address: str, namespace: str, run_worker: bool):
        from temporalio.client import Client
        from temporalio.worker import Worker

        from app.adapters.temporal_activities import CoordinationActivities
        from app.adapters.temporal_workflows import CoordinationWorkflow

        async with asyncio.timeout(8):
            self.client = await Client.connect(address, namespace=namespace)
        if run_worker:
            activities = CoordinationActivities(self.coordinator)
            self.worker = Worker(
                self.client,
                task_queue=self.task_queue,
                workflows=[CoordinationWorkflow],
                activities=[activities.analyze, activities.advance, activities.expire],
                activity_executor=self.executor,
            )
            self.worker_task = asyncio.create_task(self.worker.run())
            self.worker_task.add_done_callback(self._worker_finished)
            # Surface immediately failed startup instead of announcing a live worker.
            await asyncio.sleep(0)
            if self.worker_task.done():
                await self.worker_task
                raise WorkflowError("Temporal worker stopped during startup")

    def _worker_finished(self, task):
        self._worker_stopped = True
        if not task.cancelled():
            task.exception()  # Retrieve fatal errors; never log credential-bearing details.

    def health(self) -> tuple[bool, str]:
        with self._lifecycle_lock:
            if self._closed or not self.thread.is_alive():
                return False, "Temporal runtime is closed"
            worker_task = self.worker_task
            if self.worker is not None and (
                self._worker_stopped or worker_task is None or worker_task.done()
            ):
                return (
                    False,
                    (
                        "Embedded Temporal worker stopped; restart the worker after "
                        "inspecting the service"
                    ),
                )
            return (
                True,
                "Temporal client initialized; worker lifecycle healthy (not a live service probe)",
            )

    def _call(self, coroutine, timeout: float = 12):
        # Close and API submissions share one mutex: a queued caller cannot submit
        # to a stopped loop after checking its state before shutdown.
        with self._lifecycle_lock:
            if self._closed or self.loop.is_closed() or not self.thread.is_alive():
                coroutine.close()
                raise WorkflowError("Temporal runtime is closed")
            future = asyncio.run_coroutine_threadsafe(coroutine, self.loop)
            try:
                return future.result(timeout=timeout)
            except Exception as exc:
                future.cancel()
                raise WorkflowError(
                    "Temporal operation failed or timed out; inspect the configured service"
                ) from exc

    async def _start(
        self,
        run_id: str,
        resume: bool = False,
        *,
        execution_id: str | None = None,
        generation: int = 0,
    ):
        from temporalio.common import WorkflowIDConflictPolicy, WorkflowIDReusePolicy
        from temporalio.exceptions import WorkflowAlreadyStartedError

        # Atomic signal-with-start also wakes an existing approval wait. A
        # separate start then signal can race with workflow completion.
        signal = (
            {
                "start_signal": "decision",
                "start_signal_args": [{"id": f"resume:{new_id()}", "payload": {"kind": "refresh"}}],
            }
            if resume
            else {}
        )
        arguments = {"args": [run_id, generation]} if generation else {"arg": run_id}
        try:
            await self.client.start_workflow(
                "cca-coordination",
                id=execution_id or run_id,
                task_queue=self.task_queue,
                **arguments,
                id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING,
                id_reuse_policy=WorkflowIDReusePolicy.ALLOW_DUPLICATE
                if resume
                else WorkflowIDReusePolicy.REJECT_DUPLICATE,
                rpc_timeout=timedelta(seconds=6),
                **signal,
            )
        except WorkflowAlreadyStartedError:
            pass  # Stable business run ID already has an execution.

    def start(self, run_id: str) -> str:
        self._dispatch(run_id, resume=False)
        return run_id

    def signal(self, run_id: str, message: dict, message_id: str) -> None:
        self._call(
            self.client.get_workflow_handle(self._execution_id(run_id)).signal(
                "decision", {"id": message_id, "payload": message}, rpc_timeout=timedelta(seconds=6)
            )
        )

    def status(self, run_id: str) -> str:
        description = self._call(
            self.client.get_workflow_handle(self._execution_id(run_id)).describe(
                rpc_timeout=timedelta(seconds=6)
            )
        )
        return description.status.name if description.status else "UNKNOWN"

    def cancel(self, run_id: str, *, generation: int | None = None) -> None:
        with self.factory.open() as repo:
            run = repo.run(run_id)
        if generation is not None and run.generation != generation:
            return
        self._call(
            self.client.get_workflow_handle(run.runtime_execution_id or run.id).cancel(
                rpc_timeout=timedelta(seconds=6)
            )
        )

    def resume(self, run_id: str) -> None:
        # Resume from persisted domain state in a new Temporal execution when closed.
        # Application operation receipts preserve side-effect identity across executions.
        self._dispatch(run_id, resume=True)

    def _execution_id(self, run_id: str) -> str:
        with self.factory.open() as repo:
            run = repo.run(run_id)
        return run.runtime_execution_id or run.id

    def _dispatch(self, run_id: str, *, resume: bool) -> None:
        with self._lifecycle_lock:
            if self._closed:
                raise WorkflowError("Temporal runtime is closed")
            run = bind_execution(self.factory, run_id, self.name)
            self._call(
                self._start(
                    run_id,
                    resume=resume,
                    execution_id=run.runtime_execution_id or run.id,
                    generation=run.generation,
                )
            )

    async def _shutdown(self):
        if self.worker is not None:
            await self.worker.shutdown()
        if self.worker_task is not None:
            await asyncio.gather(self.worker_task, return_exceptions=True)

    def close(self) -> None:
        with self._lifecycle_lock:
            if self._closed:
                return
            try:
                self._call(self._shutdown(), timeout=10)
            finally:
                self._closed = True
                self.loop.call_soon_threadsafe(self.loop.stop)
                self.thread.join(timeout=3)
                self.executor.shutdown(wait=False, cancel_futures=True)
