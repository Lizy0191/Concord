"""Regression tests for issues found while continuing checkpoint 03."""

import hashlib
from concurrent.futures import ThreadPoolExecutor

import pytest
from app.adapters.persistence.tables import DocumentRow
from app.domain.errors import ProviderError
from app.domain.events import ProjectEvent
from app.ports.providers import DocumentChunk
from sqlalchemy.orm import Session


def proposal_for(services, admin):
    event = ProjectEvent(
        project_id="harbor-east",
        work_package_id="WP-200",
        kind="design_revision",
        title="Continuation regression",
        change={"revision": "V17"},
    )
    run = services.coordination.ingest(event, admin)
    services.runtime.start(run.id)
    with services.factory.open() as repo:
        return run, repo.proposals(run.id)[0]


def test_approval_retry_returns_same_record_even_concurrently(services, admin):
    run, proposal = proposal_for(services, admin)
    with ThreadPoolExecutor(max_workers=4) as pool:
        approvals = list(pool.map(lambda _: services.actions.approve(proposal.id, admin), range(8)))
    assert len({approval.id for approval in approvals}) == 1
    with services.factory.open() as repo:
        assert len(repo.approvals(proposal.id)) == 1
        events = [
            event for event in repo.stream(run.id) if event.payload.get("name") == "action-approved"
        ]
        assert len(events) == 1


def test_cancel_completed_run_does_not_cancel_runtime_or_lie(client, services, monkeypatch):
    run = client.get("/api/projects/harbor-east/workspace").json()["run"]
    assert run["status"] == "COMPLETED"
    calls = []
    monkeypatch.setattr(services.runtime, "cancel", calls.append)
    result = client.post(f"/api/runs/{run['id']}/cancel")
    assert result.status_code == 200
    assert result.json()["status"] == "COMPLETED"
    assert calls == []


def test_document_download_refuses_content_changed_after_import(client, services):
    response = client.post(
        "/api/projects/harbor-east/documents",
        files={"file": ("hash-bound.md", b"# Bound evidence\nOriginal bytes")},
    )
    assert response.status_code == 202
    job = client.get(f"/api/jobs/{response.json()['id']}").json()
    document_id = job["request"]["document_id"]
    with Session(services.factory.engine) as session:
        row = session.get(DocumentRow, document_id)
        services.storage.put(row.object_key, b"Tampered bytes")
    result = client.get(f"/api/documents/{document_id}/content")
    assert result.status_code == 502
    assert "hash" in result.json()["detail"].lower()


@pytest.mark.parametrize(
    "bad_hash,duplicate,empty", [(True, False, False), (False, True, False), (False, False, True)]
)
def test_parser_output_must_preserve_hash_unique_ids_and_text(
    services, monkeypatch, bad_hash, duplicate, empty
):
    content = b"# Original source"
    chunk = DocumentChunk(
        id="boundary-chunk",
        text="" if empty else "Original source",
        source_hash="bad" if bad_hash else hashlib.sha256(content).hexdigest(),
        parser="contract-parser",
        location="paragraph 1",
    )
    monkeypatch.setattr(
        services.documents.parser, "parse", lambda *_: [chunk, chunk] if duplicate else [chunk]
    )
    with pytest.raises(ProviderError):
        services.documents.import_file("harbor-east", "boundary.md", content, "boundary-doc")
    with Session(services.factory.engine) as session:
        assert session.get(DocumentRow, "boundary-doc") is None


@pytest.mark.parametrize(
    "path",
    [
        "/api/documents/missing/chunks",
        "/api/projects/missing/documents",
        "/api/projects/missing/search?q=hello",
    ],
)
def test_unknown_document_resources_are_not_successful_empty_results(client, path):
    assert client.get(path).status_code == 404


@pytest.mark.parametrize("cursor", ["-1", "nan", "1.5", "9007199254740992"])
def test_sse_rejects_invalid_or_javascript_unsafe_cursor(client, cursor):
    run = client.get("/api/projects/harbor-east/workspace").json()["run"]
    response = client.get(f"/api/runs/{run['id']}/events", headers={"Last-Event-ID": cursor})
    assert response.status_code == 409


@pytest.mark.parametrize("terminal_status", ["CANCELLED", "EXPIRED"])
def test_receipt_retry_cannot_resurrect_a_concurrently_stopped_run(
    client, services, admin, monkeypatch, terminal_status
):
    from contextlib import contextmanager

    run, proposal = proposal_for(services, admin)
    services.actions.approve(proposal.id, admin)
    receipt = services.actions._execute_locked(proposal.id, proposal.project_id, admin)
    with services.factory.open(run.project_id, write=True) as repo:
        current = repo.run(run.id)
        repo.save_run(
            current.model_copy(update={"status": "FAILED", "error": "recheck interrupted"})
        )

    original_open = services.factory.open
    intercepted = False

    @contextmanager
    def concurrent_stop(project_id=None, write=False):
        nonlocal intercepted
        if write and not intercepted:
            intercepted = True
            # Another request wins immediately before this request's project lock.
            with original_open(run.project_id, write=True) as repo:
                current = repo.run(run.id)
                repo.save_run(current.model_copy(update={"status": terminal_status}))
        with original_open(project_id, write=write) as repo:
            yield repo

    monkeypatch.setattr(services.factory, "open", concurrent_stop)
    dispatched = []
    monkeypatch.setattr(services.runtime, "resume", lambda *args: dispatched.append(args))
    monkeypatch.setattr(services.runtime, "signal", lambda *args: dispatched.append(args))
    response = client.post(f"/api/proposals/{proposal.id}/execute")
    assert response.status_code == 202
    assert response.json()["queued"] is False
    with original_open() as repo:
        assert repo.run(run.id).status == terminal_status
        assert repo.execution(proposal.operation_id) == receipt
    assert dispatched == []
