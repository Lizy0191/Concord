"""Bounded timeline reads and authenticated resumable SSE transport."""

import asyncio
import json

from fastapi import APIRouter, Depends, Header, Query, Request
from fastapi.responses import StreamingResponse

from app.api.auth import CurrentUser, services
from app.domain.errors import Conflict
from app.domain.runs import TERMINAL_STATUSES, StreamEvent
from app.policies.actions import require

router = APIRouter()


@router.get("/runs/{run_id}/timeline", response_model=list[StreamEvent])
def timeline(
    run_id: str,
    user: CurrentUser,
    after: int = Query(default=0, ge=0, le=2**53 - 1),
    tail: int | None = Query(default=None, ge=1, le=200),
    svc=Depends(services),
):
    require(user, "read")
    if tail is not None and after:
        raise Conflict("Choose a replay cursor or a latest-event window, not both")
    with svc.factory.open() as repo:
        repo.run(run_id)
        return repo.stream_tail(run_id, tail) if tail is not None else repo.stream(run_id, after)


@router.get("/runs/{run_id}/events")
async def event_stream(
    run_id: str,
    request: Request,
    user: CurrentUser,
    last_event_id: str | None = Header(default=None),
    svc=Depends(services),
):
    require(user, "read")
    try:
        cursor = int(last_event_id or "0")
        if not 0 <= cursor <= 2**53 - 1:
            raise ValueError("cursor outside the interoperable integer range")
    except ValueError as exc:
        raise Conflict("Last-Event-ID must be a nonnegative safe integer") from exc
    with svc.factory.open() as repo:
        repo.run(run_id)

    async def stream():
        nonlocal cursor
        heartbeat = 0
        while not await request.is_disconnected():

            def read_batch(cursor=cursor):
                with svc.factory.open() as repo:
                    # Read status first: a terminal commit also contains its
                    # final frames. Reading frames first can observe an empty
                    # batch followed by the new terminal status and drop them.
                    status = repo.run(run_id).status
                    return repo.stream(run_id, cursor), status

            rows, status = await asyncio.to_thread(read_batch)
            for row in rows:
                cursor = row.sequence
                yield f"id: {cursor}\ndata: {json.dumps(row.payload)}\n\n"
            if status in TERMINAL_STATUSES and len(rows) < 200:
                break
            heartbeat += 1
            if heartbeat % 40 == 0:
                yield ": keepalive\n\n"
            await asyncio.sleep(0.25)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
