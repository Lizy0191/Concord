from concurrent.futures import ThreadPoolExecutor

import pytest
from app.domain.actions import Principal
from app.domain.errors import (
    ApprovalRequired,
    Conflict,
    PermissionDenied,
    ProviderError,
    StaleSnapshotError,
)
from app.domain.events import ProjectEvent
from app.domain.runs import ReasoningProposal


def ingest(services, admin, kind="design_revision", change=None, wp="WP-200"):
    event = ProjectEvent(
        project_id="harbor-east",
        work_package_id=wp,
        kind=kind,
        title="Test revision",
        change=change or {"revision": "V17"},
    )
    run = services.coordination.ingest(event, admin)
    services.runtime.start(run.id)
    with services.factory.open() as repo:
        current = repo.run(run.id)
        proposal = repo.proposals(run.id)[0]
    return current, proposal, event


def test_design_approval_execution_recheck_is_real(services, admin):
    run, proposal, event = ingest(services, admin)
    assert run.status == "WAITING_APPROVAL"
    with pytest.raises(ApprovalRequired):
        services.actions.execute(proposal.id, admin)
    approval = services.actions.approve(proposal.id, admin)
    assert approval.level == "standard"
    receipt = services.actions.execute(proposal.id, admin)
    assert receipt.after_version == receipt.before_version + 1
    with services.factory.open() as repo:
        state = repo.state("harbor-east")
        fresh = repo.latest_analysis("harbor-east")
        assert state.package("WP-200").accepted_revision == "V17"
        assert fresh.snapshot.version == state.version
        assert fresh.snapshot.id != proposal.snapshot_id
        assert all(item.status == "READY" for item in fresh.readiness)
        assert repo.run(run.id).status == "COMPLETED"
        assert {"ACTION_APPROVED", "ACTION_VERIFIED", "ANALYSIS_RECHECK"}.issubset(
            {a.action for a in repo.audits("harbor-east")}
        )
        types = {e.payload["type"] for e in repo.stream(run.id)}
        assert {
            "RUN_STARTED",
            "STATE_SNAPSHOT",
            "STEP_STARTED",
            "STEP_FINISHED",
            "RUN_FINISHED",
            "CUSTOM",
        }.issubset(types)


def test_secondary_workforce_uses_same_core(services, admin):
    run, proposal, _ = ingest(services, admin, "workforce", {"available_workers": 1}, "WP-300")
    assert proposal.resolution.effects[0].kind == "assign_crew"
    services.actions.approve(proposal.id, admin)
    services.actions.execute(proposal.id, admin)
    with services.factory.open() as repo:
        assert repo.state("harbor-east").package("WP-300").available_workers == 3
        assert repo.run(run.id).status == "COMPLETED"


def test_stale_snapshot_blocks_execution_and_recomputes(services, admin):
    run, proposal, _ = ingest(services, admin)
    services.actions.approve(proposal.id, admin)
    next_event = ProjectEvent(
        project_id="harbor-east",
        work_package_id="WP-200",
        kind="design_revision",
        title="V18 arrives",
        change={"revision": "V18"},
    )
    services.coordination.ingest(next_event, admin)
    with pytest.raises(StaleSnapshotError):
        services.actions.execute(proposal.id, admin)
    with services.factory.open() as repo:
        state = repo.state("harbor-east")
        assert repo.execution(proposal.operation_id) is None
        assert state.package("WP-200").accepted_revision == "V16"
        fresh = repo.latest_analysis("harbor-east")
        assert fresh.snapshot.version == state.version
        assert any("V18" in c.description for c in fresh.constraints)


def test_r4_strong_human_approval(services, admin):
    run, proposal, _ = ingest(services, admin, "inspection", {"inspection_passed": False})
    assert proposal.risk == 4
    with pytest.raises(PermissionDenied):
        services.actions.approve(proposal.id, admin)
    ordinary = Principal(id="ordinary", role="approver")
    with pytest.raises(PermissionDenied):
        services.actions.approve(proposal.id, ordinary, True, "APPROVE R4")
    services.actions.approve(proposal.id, admin, True, "APPROVE R4")
    assert services.actions.execute(proposal.id, admin).status == "VERIFIED"


def test_duplicate_concurrent_retry_does_not_repeat_side_effect(services, admin):
    _, proposal, _ = ingest(services, admin)
    services.actions.approve(proposal.id, admin)
    with ThreadPoolExecutor(max_workers=4) as pool:
        receipts = list(pool.map(lambda _: services.actions.execute(proposal.id, admin), range(4)))
    assert all(r == receipts[0] for r in receipts)
    with services.factory.open() as repo:
        assert repo.state("harbor-east").version == receipts[0].after_version
        assert len([a for a in repo.audits("harbor-east") if a.action == "ACTION_VERIFIED"]) == 1


def test_event_idempotency_and_conflict(services, admin):
    run, _, event = ingest(services, admin)
    assert services.coordination.ingest(event, admin).id == run.id
    with pytest.raises(Conflict):
        services.coordination.ingest(event.model_copy(update={"title": "different"}), admin)


def test_model_failure_keeps_authoritative_state(services, admin):
    class BrokenReasoning:
        def interpret(self, *_):
            raise ProviderError("Controlled test failure")

    event = ProjectEvent(
        project_id="harbor-east",
        work_package_id="WP-200",
        kind="design_revision",
        title="V17",
        change={"revision": "V17"},
    )
    run = services.coordination.ingest(event, admin)
    with services.factory.open() as repo:
        before = repo.state("harbor-east")
    services.analysis.reasoning = BrokenReasoning()
    with pytest.raises(ProviderError):
        services.runtime.start(run.id)
    with services.factory.open() as repo:
        assert repo.state("harbor-east") == before
        assert repo.run(run.id).status == "FAILED"
        assert not repo.proposals(run.id)


def test_receipt_recovers_crash_before_recheck(services, admin, monkeypatch):
    run, proposal, _ = ingest(services, admin)
    services.actions.approve(proposal.id, admin)
    real = services.analysis.analyze

    def crash(_, *, generation=None):
        raise ProviderError("Recheck temporarily unavailable")

    monkeypatch.setattr(services.analysis, "analyze", crash)
    with pytest.raises(ProviderError):
        services.actions.execute(proposal.id, admin)
    with services.factory.open() as repo:
        receipt = repo.execution(proposal.operation_id)
        assert receipt is not None
    monkeypatch.setattr(services.analysis, "analyze", real)
    assert services.actions.execute(proposal.id, admin) == receipt
    with services.factory.open() as repo:
        assert repo.run(run.id).status == "COMPLETED"
        assert repo.state("harbor-east").version == receipt.after_version


def test_unknown_model_evidence_is_rejected(services, admin):
    class InventedEvidence:
        def interpret(self, *_):
            return ReasoningProposal(
                summary="Claim", evidence_ids=("not-in-snapshot",), mode="test"
            )

    run, proposal, _ = ingest(services, admin)
    services.analysis.reasoning = InventedEvidence()
    with pytest.raises(ProviderError):
        services.analysis.analyze(run.id)


def test_viewer_cannot_approve_execute_or_ingest(services, admin):
    _, proposal, event = ingest(services, admin)
    viewer = Principal(id="viewer", role="viewer")
    for action in [
        lambda: services.actions.approve(proposal.id, viewer),
        lambda: services.actions.execute(proposal.id, viewer),
        lambda: services.coordination.ingest(event, viewer),
    ]:
        with pytest.raises(PermissionDenied):
            action()
