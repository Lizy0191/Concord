"""SSE replay is bounded, complete, and safe when a terminal commit races a poll."""

import json
from contextlib import contextmanager

from app.domain.runs import AgentRun


def test_terminal_commit_between_poll_queries_cannot_drop_final_frames(
    client, services, monkeypatch
):
    with services.factory.open("harbor-east", write=True) as repo:
        run = AgentRun(project_id="harbor-east", status="RUNNING")
        repo.save_run(run)
    original_open = services.factory.open
    intercepted = False

    @contextmanager
    def wrapped_open(*args, **kwargs):
        with original_open(*args, **kwargs) as repo:
            real_stream = repo.stream

            def stream(run_id, after=0):
                nonlocal intercepted
                rows = real_stream(run_id, after)
                if run_id == run.id and not intercepted:
                    intercepted = True
                    # The producer commits after this poll read the old event set.
                    with original_open("harbor-east", write=True) as writer:
                        current = writer.run(run.id)
                        writer.emit(run.id, {"type": "RUN_FINISHED"})
                        writer.save_run(current.model_copy(update={"status": "COMPLETED"}))
                return rows

            repo.stream = stream
            yield repo

    monkeypatch.setattr(services.factory, "open", wrapped_open)
    response = client.get(f"/api/runs/{run.id}/events")
    assert response.status_code == 200
    assert '"RUN_FINISHED"' in response.text


def test_sse_drains_more_than_one_batch_and_replays_after_cursor(client, services):
    with services.factory.open("harbor-east", write=True) as repo:
        run = AgentRun(project_id="harbor-east", status="COMPLETED")
        repo.save_run(run)
        for index in range(425):
            repo.emit(run.id, {"type": "CUSTOM", "name": "fixture", "value": {"index": index}})
        repo.emit(run.id, {"type": "RUN_FINISHED"})
    response = client.get(f"/api/runs/{run.id}/events")
    frames = [frame for frame in response.text.split("\n\n") if frame.startswith("id:")]
    assert len(frames) == 426
    cursor = frames[199].splitlines()[0][4:]
    replay = client.get(f"/api/runs/{run.id}/events", headers={"Last-Event-ID": cursor})
    remaining = [f for f in replay.text.split("\n\n") if f.startswith("id:")]
    assert remaining == frames[200:]
    assert json.loads(remaining[-1].split("data: ", 1)[1])["type"] == "RUN_FINISHED"


def test_timeline_latest_window_and_cursor_have_distinct_bounded_semantics(client, services):
    with services.factory.open("harbor-east", write=True) as repo:
        run = AgentRun(project_id="harbor-east", status="COMPLETED")
        repo.save_run(run)
        for index in range(250):
            repo.emit(run.id, {"type": "CUSTOM", "index": index})
    endpoint = f"/api/runs/{run.id}/timeline"
    leading = client.get(endpoint).json()
    tail = client.get(endpoint + "?tail=200").json()
    assert [row["payload"]["index"] for row in leading] == list(range(200))
    assert [row["payload"]["index"] for row in tail] == list(range(50, 250))
    assert client.get(endpoint + "?tail=1").json() == tail[-1:]
    assert client.get(endpoint + "?tail=201").status_code == 422
    assert client.get(endpoint + "?after=-1").status_code == 422
    assert client.get(endpoint + "?after=1&tail=10").status_code == 409
