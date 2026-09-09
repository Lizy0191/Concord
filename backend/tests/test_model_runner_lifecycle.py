"""Exercise the actual adapter-owned asyncio loop and worker threads."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest
from app.adapters.model_runner import ModelCallRunner
from app.domain.errors import ProviderError


def test_close_cancels_pending_call_with_provider_error():
    runner = ModelCallRunner()
    entered = Event()

    async def pending():
        entered.set()
        await asyncio.sleep(60)

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(runner.call, pending())
        try:
            assert entered.wait(3)
            runner.close()
            with pytest.raises(ProviderError, match="closed|cancelled"):
                future.result(timeout=3)
        finally:
            runner.close()
    assert not runner._thread.is_alive()


def test_shutdown_cannot_interleave_between_loop_check_and_submission(monkeypatch):
    runner = ModelCallRunner()
    entered, release, closing, closed = Event(), Event(), Event(), Event()
    original = asyncio.run_coroutine_threadsafe

    def pause_submission(coroutine, loop):
        entered.set()
        assert release.wait(3)
        return original(coroutine, loop)

    def close():
        closing.set()
        runner.close()
        closed.set()

    async def value():
        return 42

    monkeypatch.setattr(asyncio, "run_coroutine_threadsafe", pause_submission)
    with ThreadPoolExecutor(max_workers=2) as pool:
        submitted = pool.submit(runner.call, value())
        assert entered.wait(3)
        stopped = pool.submit(close)
        try:
            assert closing.wait(3)
            assert not closed.wait(0.05), "Shutdown passed an in-flight submission"
        finally:
            release.set()
        try:
            assert submitted.result(timeout=3) == 42
        except ProviderError:
            pass  # A submitted call may be cancelled by the following shutdown.
        stopped.result(timeout=3)
    assert not runner._thread.is_alive()


def test_closed_runner_closes_unscheduled_coroutine():
    runner = ModelCallRunner()
    runner.close()

    async def unused():
        return 1

    coroutine = unused()
    with pytest.raises(ProviderError, match="closed"):
        runner.call(coroutine)
    assert coroutine.cr_frame is None
