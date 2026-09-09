import pytest
from app.adapters.bim_ifc import IfcOpenShellBIMProvider
from app.adapters.storage_s3 import S3CompatibleFileStore
from app.domain.errors import CapabilityUnavailable, ProviderError
from app.domain.events import ProjectEvent
from app.domain.runs import AgentRun
from test_coordination import ingest


def test_stale_approval_refreshes_through_runtime(client, services, admin):
    run, proposal, _ = ingest(services, admin)
    services.coordination.ingest(
        ProjectEvent(
            project_id="harbor-east",
            work_package_id="WP-200",
            kind="design_revision",
            title="V18",
            change={"revision": "V18"},
        ),
        admin,
    )
    response = client.post(f"/api/proposals/{proposal.id}/approve", json={})
    assert response.status_code == 409 and response.json()["code"] == "STALE_RESULT"
    with services.factory.open() as repo:
        assert not repo.approvals(proposal.id)
        assert (
            repo.latest_analysis("harbor-east").snapshot.version
            == repo.state("harbor-east").version
        )
        assert repo.state("harbor-east").package("WP-200").accepted_revision == "V16"
        assert repo.run(run.id).status == "WAITING_APPROVAL"


def test_api_receipt_recovers_committed_effect_without_repeating_it(
    client, services, admin, monkeypatch
):
    run, proposal, _ = ingest(services, admin)
    services.actions.approve(proposal.id, admin)
    original = services.analysis.analyze

    def fail(_, *, generation=None):
        raise ProviderError("Recheck failed after commit")

    monkeypatch.setattr(services.analysis, "analyze", fail)
    response = client.post(f"/api/proposals/{proposal.id}/execute")
    assert response.status_code == 502
    with services.factory.open() as repo:
        receipt = repo.execution(proposal.operation_id)
        assert receipt and repo.run(run.id).status == "FAILED"
    monkeypatch.setattr(services.analysis, "analyze", original)
    response = client.post(f"/api/proposals/{proposal.id}/execute")
    assert response.status_code == 202 and response.json()["queued"]
    assert client.get(f"/api/operations/{proposal.operation_id}").json() == receipt.model_dump(
        mode="json"
    )
    with services.factory.open() as repo:
        assert repo.run(run.id).status == "COMPLETED"
        assert repo.state("harbor-east").version == receipt.after_version
        assert len([a for a in repo.audits("harbor-east") if a.action == "ACTION_VERIFIED"]) == 1


def test_event_replay_is_not_limited_to_ui_history_window(services, admin):
    run, _, event = ingest(services, admin)
    with services.factory.open("harbor-east", write=True) as repo:
        for _ in range(205):
            repo.save_run(AgentRun(project_id="harbor-east", status="COMPLETED"))
    assert services.coordination.ingest(event, admin).id == run.id


def test_optional_clients_are_lazy_and_fail_closed(tmp_path):
    s3 = S3CompatibleFileStore("localhost:9000", "bucket", "", "")
    with pytest.raises(CapabilityUnavailable):
        s3.put("safe/object", b"hello")
    bim = IfcOpenShellBIMProvider(tmp_path / "missing.ifc")
    with pytest.raises(CapabilityUnavailable):
        bim.elements()


def test_capabilities_probe_is_explicit_non_destructive(client):
    result = client.get("/api/capabilities?probe=true")
    assert result.status_code == 200
    capabilities = {item["name"]: item for item in result.json()["capabilities"]}
    assert capabilities["database"]["service_reachable"] is True
    assert capabilities["storage"]["service_reachable"] is True
    assert capabilities["BIM viewer"]["service_reachable"] is None
    assert "not asserted" in capabilities["BIM viewer"]["reason"]


def test_same_json_event_retry_preserves_timestamp_snapshot_and_proposals(client):
    import uuid

    body = {
        "id": str(uuid.uuid4()),
        "project_id": "harbor-east",
        "work_package_id": "WP-200",
        "kind": "design_revision",
        "title": "Retried network request",
        "change": {"revision": "V17"},
    }
    first = client.post("/api/projects/harbor-east/events", json=body)
    assert first.status_code == 202
    before = client.get("/api/projects/harbor-east/workspace").json()
    second = client.post("/api/projects/harbor-east/events", json=body)
    assert second.status_code == 202
    after = client.get("/api/projects/harbor-east/workspace").json()
    assert first.json()["id"] == second.json()["id"]
    assert before["state"] == after["state"]
    assert before["analysis"]["snapshot"]["id"] == after["analysis"]["snapshot"]["id"]
    assert before["proposals"] == after["proposals"]
    body["observed_at"] = "2026-01-01T00:00:00Z"
    assert client.post("/api/projects/harbor-east/events", json=body).status_code == 409
