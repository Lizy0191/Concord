"""Cross-family publication must keep the factory's original transaction boundary."""

import pytest
from app.domain.actions import Approval, AuditRecord
from test_coordination import ingest


@pytest.mark.parametrize("abort", [False, True], ids=["commit", "rollback"])
def test_record_groups_share_one_atomic_transaction(services, admin, abort):
    run, proposal, _ = ingest(services, admin)
    project = run.project_id
    with services.factory.open() as repo:
        state = repo.state(project)
        audits = repo.audits(project)
        stream = repo.stream(run.id)
    approval = Approval(
        proposal_id=proposal.id,
        principal_id=admin.id,
        principal_role=admin.role,
        level="standard",
    )
    audit = AuditRecord(project_id=project, actor=admin.id, action="TRANSACTION_TEST")

    def publish():
        with services.factory.open(project, write=True) as repo:
            repo.save_state(state.model_copy(update={"version": state.version + 1}))
            repo.save_run(run.model_copy(update={"status": "FAILED"}))
            repo.save_approval(approval)
            repo.audit(audit)
            repo.emit(run.id, {"type": "CUSTOM", "name": "transaction-test"})
            if abort:
                raise RuntimeError("Abort after writes in every record family")

    if abort:
        with pytest.raises(RuntimeError, match="Abort after writes"):
            publish()
    else:
        publish()

    with services.factory.open() as repo:
        if abort:
            assert repo.state(project) == state
            assert repo.run(run.id) == run
            assert repo.approvals(proposal.id) == []
            assert repo.audits(project) == audits
            assert repo.stream(run.id) == stream
        else:
            assert repo.state(project).version == state.version + 1
            assert repo.run(run.id).status == "FAILED"
            assert repo.approvals(proposal.id) == [approval]
            assert audit in repo.audits(project)
            assert repo.stream(run.id)[-1].payload["name"] == "transaction-test"
