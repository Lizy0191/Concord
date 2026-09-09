"""Actual threads/async tasks with minimal SDK doubles, NOT a Temporal server run."""

import asyncio
import sys
from concurrent.futures import ThreadPoolExecutor
from threading import Event, get_ident
from types import ModuleType, SimpleNamespace

import pytest
from app.adapters.runtime_temporal import TemporalRuntime
from app.domain.errors import WorkflowError


@pytest.fixture
def temporal_sdk(monkeypatch):
    control = SimpleNamespace(
        connect_error=False, startup_error=False, startup_exit=False, workers=[]
    )

    class Client:
        @classmethod
        async def connect(cls, address, *, namespace):
            assert address == "127.0.0.1:7233" and namespace == "test"
            if control.connect_error:
                raise RuntimeError("private connection details")
            return cls()

    class Worker:
        def __init__(self, client, *, task_queue, workflows, activities, activity_executor):
            assert task_queue == "contracts" and len(activities) == 3
            self.event = asyncio.Event()
            self.fatal = False
            control.workers.append(self)

        async def run(self):
            if control.startup_error:
                raise RuntimeError("private startup details")
            if control.startup_exit:
                return
            await self.event.wait()
            if self.fatal:
                raise RuntimeError("private worker details")

        async def shutdown(self):
            self.event.set()

    sdk, client, worker = (
        ModuleType("temporalio"),
        ModuleType("temporalio.client"),
        ModuleType("temporalio.worker"),
    )
    sdk.client, sdk.worker = client, worker
    client.Client, worker.Worker = Client, Worker
    activities, workflows = (
        ModuleType("app.adapters.temporal_activities"),
        ModuleType("app.adapters.temporal_workflows"),
    )
    activities.CoordinationActivities = lambda coordinator: SimpleNamespace(
        analyze=lambda: None, advance=lambda: None, expire=lambda: None
    )
    workflows.CoordinationWorkflow = type("CoordinationWorkflow", (), {})
    for name, module in [
        ("temporalio", sdk),
        ("temporalio.client", client),
        ("temporalio.worker", worker),
        ("app.adapters.temporal_activities", activities),
        ("app.adapters.temporal_workflows", workflows),
    ]:
        monkeypatch.setitem(sys.modules, name, module)
    return control


def construct():
    return TemporalRuntime(
        object(), "127.0.0.1:7233", "test", "contracts", factory=SimpleNamespace()
    )


@pytest.mark.parametrize("failure", ["connect_error", "startup_error", "startup_exit"])
def test_temporal_failed_initialization_closes_its_actual_event_loop(
    temporal_sdk, monkeypatch, failure
):
    created = []
    original = asyncio.new_event_loop

    def tracked_loop():
        loop = original()
        created.append(loop)
        return loop

    monkeypatch.setattr(asyncio, "new_event_loop", tracked_loop)
    setattr(temporal_sdk, failure, True)
    with pytest.raises(WorkflowError, match="operation failed") as error:
        construct()
    assert "private" not in str(error.value)
    assert len(created) == 1 and created[0].is_closed()


def test_temporal_fatal_worker_is_visible_and_close_still_releases_resources(temporal_sdk):
    runtime = construct()
    assert runtime.health()[0]

    async def fail():
        runtime.worker.fatal = True
        runtime.worker.event.set()
        await asyncio.gather(runtime.worker_task, return_exceptions=True)
        await asyncio.sleep(0)

    runtime._call(fail())
    healthy, reason = runtime.health()
    assert not healthy and "stopped" in reason and "private" not in reason
    runtime.close()
    runtime.close()
    assert not runtime.thread.is_alive() and runtime.loop.is_closed()
    assert runtime.health()[0] is False


def test_temporal_call_timeout_cancels_submission_not_the_worker(temporal_sdk):
    runtime = construct()
    try:
        with pytest.raises(WorkflowError, match="timed out"):
            runtime._call(asyncio.sleep(20), timeout=0.02)
        assert runtime._call(asyncio.sleep(0, result="next request")) == "next request"
        assert runtime.health()[0]
    finally:
        runtime.close()


def test_temporal_close_wins_against_waiting_submission(temporal_sdk):
    runtime = construct()
    lock = runtime._lifecycle_lock
    attempting, main_thread = Event(), get_ident()

    class ObservedLock:
        def __enter__(self):
            if get_ident() != main_thread:
                attempting.set()
            lock.acquire()
            return self

        def __exit__(self, *_):
            lock.release()

    runtime._lifecycle_lock = ObservedLock()
    with ThreadPoolExecutor(max_workers=1) as pool:
        with lock:
            future = pool.submit(runtime._call, asyncio.sleep(0))
            assert attempting.wait(timeout=2)
            runtime.close()
        with pytest.raises(WorkflowError, match="closed"):
            future.result(timeout=2)
    assert not runtime.thread.is_alive() and runtime.loop.is_closed()


def test_capabilities_does_not_hide_a_stopped_temporal_worker(temporal_sdk, services, monkeypatch):
    from app.adapters.capabilities import capabilities

    runtime = construct()
    try:

        async def stop():
            runtime.worker.event.set()
            await runtime.worker_task

        runtime._call(stop())
        monkeypatch.setattr(
            services,
            "settings",
            services.settings.model_copy(
                update={"diagnostic_runtime": False, "runtime": "temporal"}
            ),
        )
        monkeypatch.setattr(services, "runtime", runtime)
        capability = next(row for row in capabilities(services) if row.name == "runtime")
        assert capability.status == "unhealthy" and "stopped" in capability.reason
        assert capability.service_reachable is None  # Local worker state, not a server probe.
    finally:
        runtime.close()
