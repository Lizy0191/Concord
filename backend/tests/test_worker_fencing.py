"""Real SQLite/thread regressions for late workers; no external runtime is simulated as live."""

from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest
from app.domain.errors import ProviderError
from app.domain.events import ProjectEvent


def queued_analysis(services, admin):
    return services.coordination.ingest(
        ProjectEvent(
            project_id="harbor-east",
            work_package_id="WP-200",
            kind="design_revision",
            title="Worker fencing",
            change={"revision": "V17"},
        ),
        admin,
    )


@pytest.mark.parametrize("category", ["analysis", "document"])
@pytest.mark.parametrize("provider_fails", [False, True])
def test_worker_from_before_cancel_resume_cannot_publish_or_fail_new_attempt(
    services, client, admin, monkeypatch, category, provider_fails
):
    entered, release = Event(), Event()
    if category == "analysis":
        run = queued_analysis(services, admin)
        provider, method = services.analysis.reasoning, "interpret"
    else:
        run = services.jobs.upload(
            "harbor-east", "fenced.md", b"# Fenced document", "document_parse", admin
        )
        provider, method = services.documents.parser, "parse"
    original = getattr(provider, method)

    def blocked(*args, **kwargs):
        entered.set()
        assert release.wait(5), "Test did not release its worker"
        if provider_fails:
            raise ProviderError("Old attempt failed")
        return original(*args, **kwargs)

    monkeypatch.setattr(provider, method, blocked)
    monkeypatch.setattr(services.runtime, "resume", lambda _: None)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(services.workflow.begin, run.id)
        try:
            assert entered.wait(5)
            assert client.post(f"/api/runs/{run.id}/cancel").json()["status"] == "CANCELLED"
            response = client.post(f"/api/runs/{run.id}/resume")
            assert response.status_code == 202
            assert response.json()["status"] == "QUEUED"
        finally:
            release.set()
        if provider_fails:
            with pytest.raises(ProviderError):
                future.result(timeout=5)
        else:
            future.result(timeout=5)
    with services.factory.open() as repo:
        assert repo.run(run.id).status == "QUEUED", "A superseded worker changed the resumed run"
        assert repo.run(run.id).analysis_id is None
        if category == "document":
            assert repo.job(run.id).result is None
            assert not repo.evidence("harbor-east", repo.job(run.id).request.document_id)
    if category == "document":
        assert not any(
            d["filename"] == "fenced.md" for d in services.documents.documents("harbor-east")
        )


def test_overlapping_analysis_retries_keep_the_winning_proposals_and_approval(
    services, admin, monkeypatch
):
    run = queued_analysis(services, admin)
    entered = [Event(), Event()]
    release = [Event(), Event()]
    original = services.analysis.reasoning.interpret
    calls = 0

    def blocked(*args):
        nonlocal calls
        index = calls
        calls += 1
        entered[index].set()
        assert release[index].wait(5)
        return original(*args)

    monkeypatch.setattr(services.analysis.reasoning, "interpret", blocked)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(services.workflow.begin, run.id)
        assert entered[0].wait(5)
        second = pool.submit(services.workflow.begin, run.id)
        try:
            assert entered[1].wait(5)
            release[0].set()
            assert first.result(timeout=5) == "WAITING_APPROVAL"
            with services.factory.open() as repo:
                winner = repo.run(run.id)
                proposals = repo.proposals(run.id)
            approval = services.actions.approve(proposals[0].id, admin)
        finally:
            release[0].set()
            release[1].set()
        assert second.result(timeout=5) == "WAITING_APPROVAL"
    with services.factory.open() as repo:
        assert repo.run(run.id).analysis_id == winner.analysis_id
        assert repo.proposals(run.id) == proposals
        assert repo.approvals(proposals[0].id) == [approval]


def test_late_failed_analysis_does_not_erase_another_workers_success(services, admin, monkeypatch):
    run = queued_analysis(services, admin)
    entered, release = Event(), Event()
    original = services.analysis.reasoning.interpret
    calls = 0

    def one_late_failure(*args):
        nonlocal calls
        calls += 1
        if calls == 1:
            entered.set()
            assert release.wait(5)
            raise ProviderError("Old overlapping retry failed")
        return original(*args)

    monkeypatch.setattr(services.analysis.reasoning, "interpret", one_late_failure)
    with ThreadPoolExecutor(max_workers=1) as pool:
        late = pool.submit(services.workflow.begin, run.id)
        try:
            assert entered.wait(5)
            assert services.workflow.begin(run.id) == "WAITING_APPROVAL"
            with services.factory.open() as repo:
                winner = repo.run(run.id)
        finally:
            release.set()
        with pytest.raises(ProviderError):
            late.result(timeout=5)
    with services.factory.open() as repo:
        assert repo.run(run.id) == winner


def test_repeated_queued_resume_keeps_one_generation(services, client, admin, monkeypatch):
    run = queued_analysis(services, admin)
    services.coordination.cancel(run.id, admin)
    monkeypatch.setattr(services.runtime, "resume", lambda _: None)
    first = client.post(f"/api/runs/{run.id}/resume").json()
    second = client.post(f"/api/runs/{run.id}/resume").json()
    assert first == second
    assert first["generation"] == 1


def test_bootstrap_recovers_committed_resume_with_resume_semantics(services, admin, monkeypatch):
    from app.adapters.runtime_diagnostic import DiagnosticRuntime
    from app.bootstrap import build_services

    run = queued_analysis(services, admin)
    with services.factory.open(run.project_id, write=True) as repo:
        repo.save_run(run.model_copy(update={"status": "QUEUED", "generation": 1}))
    settings = services.settings
    services.close()
    dispatched = []
    monkeypatch.setattr(
        DiagnosticRuntime, "start", lambda self, identity: dispatched.append(("start", identity))
    )
    monkeypatch.setattr(
        DiagnosticRuntime, "resume", lambda self, identity: dispatched.append(("resume", identity))
    )
    recovered = build_services(settings)
    try:
        assert dispatched == [("resume", run.id)]
    finally:
        recovered.close()


def test_execute_from_before_cancel_resume_cannot_apply_in_new_generation(services, admin):
    run = queued_analysis(services, admin)
    services.workflow.begin(run.id)
    with services.factory.open() as repo:
        proposal = repo.proposals(run.id)[0]
        before = repo.state(run.project_id)
    services.actions.approve(proposal.id, admin)
    old_message = {
        "kind": "execute",
        "proposal_id": proposal.id,
        "principal": admin.model_dump(),
        "generation": 0,
    }
    services.coordination.cancel(run.id, admin)
    with services.factory.open(run.project_id, write=True) as repo:
        current = repo.run(run.id)
        repo.save_run(current.model_copy(update={"status": "QUEUED", "generation": 1}))
    services.workflow.begin(run.id)
    services.workflow.advance(run.id, old_message)
    with services.factory.open() as repo:
        assert repo.execution(proposal.operation_id) is None
        assert repo.state(run.project_id) == before


def test_terminal_run_execution_is_rejected_before_dispatch(services, client, admin, monkeypatch):
    run = queued_analysis(services, admin)
    services.workflow.begin(run.id)
    with services.factory.open() as repo:
        proposal = repo.proposals(run.id)[0]
    services.actions.approve(proposal.id, admin)
    services.coordination.cancel(run.id, admin)
    dispatched = []
    monkeypatch.setattr(services.runtime, "signal", lambda *args: dispatched.append(args))
    assert client.post(f"/api/proposals/{proposal.id}/execute").status_code == 409
    assert not dispatched


def test_workspace_exposes_the_analysis_owner_even_when_latest_run_is_an_import(
    services, client, admin
):
    run = queued_analysis(services, admin)
    services.workflow.begin(run.id)
    imported = services.jobs.upload(
        "harbor-east", "latest.md", b"# Source", "document_parse", admin
    )
    services.workflow.begin(imported.id)
    workspace = client.get("/api/projects/harbor-east/workspace").json()
    assert workspace["run"]["id"] == imported.id
    assert workspace["analysis_run"]["id"] == run.id
    assert workspace["analysis_run"]["status"] == "WAITING_APPROVAL"
    assert all(proposal["run_id"] == run.id for proposal in workspace["proposals"])


def test_authorized_message_cannot_rebind_to_a_later_generation(
    services, client, admin, monkeypatch
):
    run = queued_analysis(services, admin)
    services.workflow.begin(run.id)
    with services.factory.open() as repo:
        proposal = repo.proposals(run.id)[0]
    services.actions.approve(proposal.id, admin)
    original = services.actions.authorize_execution

    def authorize_then_resume(*args):
        generation = original(*args)
        services.coordination.cancel(run.id, admin)
        with services.factory.open(run.project_id, write=True) as repo:
            current = repo.run(run.id)
            repo.save_run(current.model_copy(update={"status": "QUEUED", "generation": 1}))
        return generation

    monkeypatch.setattr(services.actions, "authorize_execution", authorize_then_resume)
    messages = []
    monkeypatch.setattr(
        services.runtime, "signal", lambda identity, message, key: messages.append(message)
    )
    assert client.post(f"/api/proposals/{proposal.id}/execute").status_code == 202
    assert messages[0]["generation"] == 0
    services.workflow.begin(run.id)
    services.workflow.advance(run.id, messages[0])
    with services.factory.open() as repo:
        assert repo.execution(proposal.operation_id) is None


@pytest.mark.parametrize(
    "failure", [ProviderError("Transient executor failure"), RuntimeError("private detail")]
)
def test_durable_activity_retry_recovers_failure_without_new_user_dispatch(
    services, admin, monkeypatch, failure
):
    run = queued_analysis(services, admin)
    services.workflow.begin(run.id)
    with services.factory.open() as repo:
        proposal = repo.proposals(run.id)[0]
        initial = repo.state(run.project_id)
    services.actions.approve(proposal.id, admin)
    original = services.actions.executor.apply
    calls = 0

    def fail_once(*args):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise failure
        return original(*args)

    monkeypatch.setattr(services.actions.executor, "apply", fail_once)
    message = {
        "kind": "execute",
        "proposal_id": proposal.id,
        "principal": admin.model_dump(),
        "generation": 0,
    }
    with pytest.raises(type(failure)):
        services.workflow.advance(run.id, message)
    with services.factory.open() as repo:
        failed = repo.run(run.id)
        assert failed.status == "FAILED"
        assert "private detail" not in (failed.error or "")
        assert repo.state(run.project_id) == initial
        assert repo.execution(proposal.operation_id) is None
    assert services.workflow.advance(run.id, message) == "COMPLETED"
    with services.factory.open() as repo:
        receipt = repo.execution(proposal.operation_id)
        assert receipt is not None
        assert repo.state(run.project_id).version == initial.version + 1
    services.workflow.advance(run.id, message)
    assert calls == 2


def test_old_durable_begin_cannot_start_a_new_generation(services, admin):
    run = queued_analysis(services, admin)
    services.coordination.cancel(run.id, admin)
    with services.factory.open(run.project_id, write=True) as repo:
        current = repo.run(run.id)
        repo.save_run(current.model_copy(update={"status": "QUEUED", "generation": 1}))
    assert services.workflow.begin(run.id, generation=0) == "QUEUED"
    with services.factory.open() as repo:
        assert repo.run(run.id).analysis_id is None


def test_old_durable_expiry_cannot_expire_a_new_generation(services, admin):
    run = queued_analysis(services, admin)
    with services.factory.open(run.project_id, write=True) as repo:
        repo.save_run(run.model_copy(update={"status": "WAITING_APPROVAL", "generation": 1}))
    assert services.workflow.expire(run.id, generation=0) == "WAITING_APPROVAL"
    with services.factory.open() as repo:
        assert repo.run(run.id).status == "WAITING_APPROVAL"


def test_old_refresh_message_cannot_start_a_new_generation(services, admin):
    run = queued_analysis(services, admin)
    with services.factory.open(run.project_id, write=True) as repo:
        repo.save_run(run.model_copy(update={"generation": 1}))
    assert services.workflow.advance(run.id, {"kind": "refresh"}, generation=0) == "QUEUED"
    with services.factory.open() as repo:
        assert repo.run(run.id).analysis_id is None


@pytest.mark.parametrize("phase", ["queued", "reanalyzed"])
@pytest.mark.parametrize("operation", ["approve", "execute"])
def test_old_proposal_cannot_be_reauthorized_after_cancel_resume(
    services, client, admin, monkeypatch, phase, operation
):
    run = queued_analysis(services, admin)
    services.workflow.begin(run.id)
    with services.factory.open() as repo:
        proposal = repo.proposals(run.id)[0]
        before = repo.state(run.project_id)
    if operation == "execute":
        services.actions.approve(proposal.id, admin)
    services.coordination.cancel(run.id, admin)
    monkeypatch.setattr(services.runtime, "resume", lambda _: None)
    assert client.post(f"/api/runs/{run.id}/resume").status_code == 202
    if phase == "reanalyzed":
        assert services.workflow.begin(run.id) == "WAITING_APPROVAL"
    response = client.post(
        f"/api/proposals/{proposal.id}/{operation}", json={} if operation == "approve" else None
    )
    assert response.status_code == 409, response.text
    with services.factory.open() as repo:
        assert repo.state(run.project_id) == before
        assert repo.execution(proposal.operation_id) is None


def test_new_generation_proposal_requires_its_own_approval(services, client, admin):
    run = queued_analysis(services, admin)
    services.workflow.begin(run.id)
    with services.factory.open() as repo:
        old = repo.proposals(run.id)[0]
    services.actions.approve(old.id, admin)
    services.coordination.cancel(run.id, admin)
    assert client.post(f"/api/runs/{run.id}/resume").status_code == 202
    current = client.get("/api/projects/harbor-east/workspace").json()
    proposal = current["proposals"][0]
    assert proposal["id"] != old.id and proposal["generation"] == 1
    assert client.post(f"/api/proposals/{proposal['id']}/execute").status_code == 403
    assert client.post(f"/api/proposals/{proposal['id']}/approve", json={}).status_code == 200
    assert client.post(f"/api/proposals/{proposal['id']}/execute").status_code == 202
    with services.factory.open() as repo:
        assert repo.execution(old.operation_id) is None
        assert repo.execution(proposal["operation_id"]) is not None
