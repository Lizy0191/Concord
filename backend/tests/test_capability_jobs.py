import hashlib
from concurrent.futures import ThreadPoolExecutor

import pytest
from app.adapters.demo import demo_state
from app.domain.errors import CapabilityUnavailable, ProviderError
from app.domain.models import Project, new_id
from app.ports.providers import BIMElement


def test_document_job_binds_source_evidence_and_runtime(client, services):
    content = b"Revision control\fNew source page"
    response = client.post(
        "/api/projects/harbor-east/documents", files={"file": ("source.md", content)}
    )
    assert response.status_code == 202
    run = response.json()
    assert run["category"] == "document_parse" and run["status"] == "COMPLETED"
    job = client.get(f"/api/jobs/{run['id']}").json()
    assert job["request"]["content_hash"] == hashlib.sha256(content).hexdigest()
    assert len(job["result"]["evidence_ids"]) == 2
    evidence = client.get(
        "/api/projects/harbor-east/evidence", params={"source_id": job["request"]["document_id"]}
    ).json()
    assert {e["page"] for e in evidence} == {1, 2}
    assert all(
        e["snapshot_id"] == job["snapshot_id"] and e["quality"] == "extracted" for e in evidence
    )
    with services.factory.open() as repo:
        snapshot = repo.snapshot(job["snapshot_id"])
        assert any(s.revision == hashlib.sha256(content).hexdigest() for s in snapshot.sources)
    assert client.get(f"/api/runs/{run['id']}/events").status_code == 200


def test_missing_parser_is_inspectable_failed_job_not_partial_state(client, services):
    class FailedParser:
        def parse(self, content, filename):
            raise CapabilityUnavailable("Fixture parser unavailable")

    services.documents.parser = FailedParser()
    before = client.get("/api/projects/harbor-east/workspace").json()["state"]
    run = client.post(
        "/api/projects/harbor-east/documents", files={"file": ("missing.pdf", b"not a pdf")}
    ).json()
    assert run["status"] == "FAILED" and "Fixture parser unavailable" in run["error"]
    assert client.get("/api/projects/harbor-east/workspace").json()["state"] == before
    job = client.get(f"/api/jobs/{run['id']}").json()
    assert job["result"] is None


def test_disabled_optimization_and_vision_fail_closed(client):
    fixture = client.get("/api/optimization/fixture")
    assert fixture.status_code == 200
    assert (
        client.post("/api/projects/harbor-east/optimization", json=fixture.json()).status_code
        == 503
    )
    assert (
        client.post(
            "/api/projects/harbor-east/vision", files={"file": ("x.png", b"abc", "image/png")}
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/projects/harbor-east/vision",
            data={"consent": "true"},
            files={"file": ("x.png", b"abc", "image/png")},
        ).status_code
        == 503
    )


def test_ifc_job_publishes_revision_only_after_success(client, services):
    class IFCFixture:
        def parse(self, content):
            return [
                BIMElement(
                    id="fixture-guid",
                    name="Wall",
                    type="IfcWall",
                    storey="L02",
                    revision=hashlib.sha256(content).hexdigest(),
                )
            ]

    services.jobs.ifc = IFCFixture()
    before = client.get("/api/projects/harbor-east/workspace").json()["state"]["version"]
    run = client.post(
        "/api/projects/harbor-east/bim/import", files={"file": ("fixture.ifc", b"contract fixture")}
    ).json()
    assert run["status"] == "COMPLETED"
    assert client.get("/api/projects/harbor-east/bim/elements").json()[0]["id"] == "fixture-guid"
    workspace = client.get("/api/projects/harbor-east/workspace").json()
    assert workspace["state"]["version"] == before + 1 and workspace["stale"] is True
    assert client.get("/api/projects/harbor-east/bim/content").content == b"contract fixture"
    client.post("/api/projects/harbor-east/recheck")
    assert not client.get("/api/projects/harbor-east/workspace").json()["stale"]
    client.post("/api/demo/reset")
    assert all(
        e["id"] != "fixture-guid"
        for e in client.get("/api/projects/harbor-east/bim/elements").json()
    )


def test_failed_ifc_does_not_publish_revision(client, services):
    class BadIFC:
        def parse(self, content):
            raise ProviderError("Malformed IFC")

    services.jobs.ifc = BadIFC()
    state = client.get("/api/projects/harbor-east/workspace").json()["state"]
    run = client.post(
        "/api/projects/harbor-east/bim/import", files={"file": ("bad.ifc", b"bad")}
    ).json()
    assert run["status"] == "FAILED"
    assert client.get("/api/projects/harbor-east/workspace").json()["state"] == state


def test_import_retry_and_concurrent_duplicate_do_not_duplicate_documents(services, admin):
    content = b"One original source"
    doc_id = new_id()
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(
                lambda _: services.documents.import_file("harbor-east", "same.md", content, doc_id),
                range(2),
            )
        )
    assert results[0]["id"] == results[1]["id"] == doc_id
    assert services.documents.content(doc_id)[1] == content
    assert len([d for d in services.documents.documents("harbor-east") if d["id"] == doc_id]) == 1
    assert len(services.documents.chunks(doc_id)) == 1


def test_cancelled_job_does_not_parse_or_publish(services, admin):
    run = services.jobs.upload("harbor-east", "safe.md", b"original", "document_parse", admin)
    services.coordination.cancel(run.id, admin)
    assert services.jobs.process(run.id) == "CANCELLED"
    with services.factory.open() as repo:
        assert repo.job(run.id).result is None


def test_changed_import_hash_is_refused(services, admin):
    run = services.jobs.upload("harbor-east", "safe.md", b"original", "document_parse", admin)
    with services.factory.open() as repo:
        job = repo.job(run.id)
    services.storage.put(job.request.object_key, b"replacement")
    with pytest.raises(ProviderError, match="hash"):
        services.workflow.begin(run.id)
    with services.factory.open() as repo:
        assert repo.run(run.id).status == "FAILED"
        assert repo.job(run.id).result is None


def test_evidence_query_is_project_scoped(client, services, admin):
    state = demo_state().model_copy(
        update={"project": Project(id="other-project", name="Other project")}
    )
    services.coordination.seed(state, admin)
    client.post(
        "/api/projects/harbor-east/events",
        json={
            "project_id": "harbor-east",
            "work_package_id": "WP-200",
            "kind": "design_revision",
            "title": "V17",
            "change": {"revision": "V17"},
        },
    )
    response = client.get("/api/projects/other-project/evidence")
    assert response.status_code == 200 and response.json() == []
    assert client.get("/api/projects/harbor-east/evidence").json()


def test_upload_checks_role_before_storage(client, services):
    files_before = len(list((services.settings.data_dir / "files").rglob("*")))
    response = client.post(
        "/api/projects/harbor-east/documents",
        headers={"Authorization": "Bearer local-demo-viewer"},
        files={"file": ("x.md", b"data")},
    )
    assert response.status_code == 403
    assert len(list((services.settings.data_dir / "files").rglob("*"))) == files_before


def test_cancel_during_document_parse_publishes_no_document_or_search_result(
    services, admin, monkeypatch
):
    content = b"cancellation-publication-regression-unique"
    run = services.jobs.upload("harbor-east", "cancel-during.md", content, "document_parse", admin)
    parse = services.documents.parser.parse

    def cancel_while_parsing(data, filename):
        assert services.coordination.cancel(run.id, admin) == "CANCELLED"
        return parse(data, filename)

    monkeypatch.setattr(services.documents.parser, "parse", cancel_while_parsing)
    assert services.workflow.begin(run.id) == "CANCELLED"
    with services.factory.open() as repo:
        job = repo.job(run.id)
        assert job.result is None
        assert repo.evidence("harbor-east", job.request.document_id) == []
    assert not any(
        doc["id"] == job.request.document_id for doc in services.documents.documents("harbor-east")
    )
    assert services.documents.search("harbor-east", content.decode()) == []


def test_document_metadata_and_fts_rollback_when_job_publication_fails(
    services, admin, monkeypatch
):
    from app.adapters.persistence.repository import SQLCoordinationRepository

    content = b"atomic-publication-regression-unique"
    run = services.jobs.upload(
        "harbor-east", "atomic-publication.md", content, "document_parse", admin
    )
    save_job = SQLCoordinationRepository.save_job

    def fail_final_publish(repo, job):
        if job.id == run.id and job.result is not None:
            raise ProviderError("Injected publication failure")
        return save_job(repo, job)

    monkeypatch.setattr(SQLCoordinationRepository, "save_job", fail_final_publish)
    with pytest.raises(ProviderError, match="publication failure"):
        services.workflow.begin(run.id)
    with services.factory.open() as repo:
        job = repo.job(run.id)
        assert repo.run(run.id).status == "FAILED"
        assert job.result is None
        assert repo.evidence("harbor-east", job.request.document_id) == []
    assert not any(
        doc["id"] == job.request.document_id for doc in services.documents.documents("harbor-east")
    )
    assert services.documents.search("harbor-east", content.decode()) == []
    monkeypatch.setattr(SQLCoordinationRepository, "save_job", save_job)
    assert services.workflow.begin(run.id) == "COMPLETED"
    assert len(services.documents.search("harbor-east", content.decode())) == 1


def test_prepared_document_is_private_until_existing_project_transaction_publishes(services):
    prepared = services.documents.prepare_file(
        "harbor-east", "staged.md", b"staged-private-evidence"
    )
    assert not any(
        item["id"] == prepared.metadata.id for item in services.documents.documents("harbor-east")
    )
    assert services.documents.search("harbor-east", "staged-private-evidence") == []
    with services.factory.open("harbor-east", write=True) as repo:
        assert repo.publish_document(prepared) == prepared
    assert len(services.documents.search("harbor-east", "staged-private-evidence")) == 1


def test_concurrent_document_job_attempts_publish_one_atomic_result(services, admin, monkeypatch):
    from threading import Barrier

    run = services.jobs.upload(
        "harbor-east", "concurrent.md", b"concurrent-job-evidence-unique", "document_parse", admin
    )
    barrier = Barrier(2, timeout=3)
    original_parse = services.documents.parser.parse

    def parallel_parse(content, filename):
        chunks = original_parse(content, filename)
        barrier.wait()
        return chunks

    monkeypatch.setattr(services.documents.parser, "parse", parallel_parse)
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(lambda _: services.jobs.process(run.id), range(2)))
    assert outcomes == ["COMPLETED", "COMPLETED"]
    with services.factory.open() as repo:
        job = repo.job(run.id)
        assert len(repo.evidence("harbor-east", job.request.document_id)) == 1
        assert (
            len(
                [
                    audit
                    for audit in repo.audits("harbor-east")
                    if audit.run_id == run.id and audit.action == "CAPABILITY_COMPLETED"
                ]
            )
            == 1
        )
        assert repo.run(run.id).status == "COMPLETED"
    assert len(services.documents.chunks(job.request.document_id)) == 1
    assert len(services.documents.search("harbor-east", "concurrent-job-evidence-unique")) == 1


def test_slower_ifc_import_cannot_replace_a_newer_published_model(services, admin, monkeypatch):
    from threading import Event

    from app.domain.errors import Conflict

    entered, release = Event(), Event()
    calls = []

    def parse(content):
        calls.append(content)
        if content == b"older":
            entered.set()
            assert release.wait(5)
        return [
            BIMElement(
                id=content.decode(),
                name="Synthetic",
                type="IfcWall",
                revision=hashlib.sha256(content).hexdigest(),
            )
        ]

    monkeypatch.setattr(services.jobs.ifc, "parse", parse)
    old = services.jobs.upload("harbor-east", "older.ifc", b"older", "bim_import", admin)
    new = services.jobs.upload("harbor-east", "newer.ifc", b"newer", "bim_import", admin)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(services.workflow.begin, old.id)
        try:
            assert entered.wait(5)
            assert services.workflow.begin(new.id) == "COMPLETED"
        finally:
            release.set()
        with pytest.raises(Conflict, match="active IFC changed"):
            future.result(timeout=5)
    with services.factory.open() as repo:
        assert repo.bim_index("harbor-east").filename == "newer.ifc"
        assert repo.run(old.id).status == "FAILED" and repo.job(old.id).result is None
        committed_version = repo.state("harbor-east").version
    with pytest.raises(Conflict, match="active IFC changed"):
        services.workflow.begin(old.id)  # An SDK retry is not permission to overwrite.
    assert calls.count(b"older") == 1
    with services.factory.open() as repo:
        assert repo.state("harbor-east").version == committed_version
    # A newly submitted import deliberately binds to the latest active revision.
    replacement = services.jobs.upload(
        "harbor-east", "replacement.ifc", b"replacement", "bim_import", admin
    )
    assert services.workflow.begin(replacement.id) == "COMPLETED"
    with services.factory.open() as repo:
        assert repo.bim_index("harbor-east").filename == "replacement.ifc"
