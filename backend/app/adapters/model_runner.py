"""One bounded asyncio loop per model adapter, reusable from synchronous worker threads.

A new asyncio.run loop per request can strand cached SDK HTTP connections on a
closed loop. Keeping calls on this adapter-owned loop avoids that lifecycle bug.
No business workflow state is stored here; DBOS/Temporal still own durability.
"""

import asyncio
from concurrent.futures import CancelledError
from threading import Event, RLock, Thread

from app.domain.errors import ProviderError


class ModelCallRunner:
    def __init__(self) -> None:
        self._lock = RLock()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: Thread | None = None
        self._closed = False

    def _ensure_started(self) -> asyncio.AbstractEventLoop:
        if self._closed:
            raise ProviderError("Model adapter is closed")
        if self._loop is None:
            loop = asyncio.new_event_loop()
            self._loop = loop
            self._thread = Thread(
                target=self._serve, args=(loop,), name="cca-model-io", daemon=True
            )
            self._thread.start()
        return self._loop

    def _serve(self, loop: asyncio.AbstractEventLoop) -> None:
        asyncio.set_event_loop(loop)
        try:
            loop.run_forever()
        finally:
            tasks = asyncio.all_tasks(loop)
            for task in tasks:
                task.cancel()
            if tasks:
                loop.run_until_complete(asyncio.gather(*tasks, return_exceptions=True))
            loop.close()

    def call(self, coroutine, timeout_seconds: float = 90):
        # Keep close outside the state transition, but do not let it stop the
        # loop before this accepted submission has been installed as a task.
        with self._lock:
            accepted = Event()

            async def accepted_coroutine():
                accepted.set()
                return await coroutine

            try:
                loop = self._ensure_started()
                future = asyncio.run_coroutine_threadsafe(accepted_coroutine(), loop)
                if not accepted.wait(3):
                    future.cancel()
                    raise ProviderError("Model adapter did not accept the submitted call")
            except Exception:
                coroutine.close()
                raise
        try:
            return future.result(timeout=timeout_seconds)
        except CancelledError as exc:
            raise ProviderError("Model adapter closed; pending call was cancelled") from exc
        except TimeoutError as exc:
            future.cancel()
            raise ProviderError("Model call exceeded its total deadline") from exc

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
            loop = self._loop
            thread = self._thread
            if loop is not None:
                loop.call_soon_threadsafe(loop.stop)
        if thread is not None:
            thread.join(timeout=3)
