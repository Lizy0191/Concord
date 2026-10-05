"""Platform invocation/publication fences with deterministic executor fixtures."""

import hashlib
import json

import pytest
from app.bootstrap import build_services
from app.domain.actions import Principal
from app.domain.comparisons import ComparisonRequest
from app.domain.engineering import Change, EngineeringPublication
from app.domain.engineering_refs import CadTarget, DrawingTarget
from app.domain.errors import (
    CapabilityUnavailable,
    Conflict,
    DomainError,
    NotFound,
    PermissionDenied,
)
from app.domain.models import Evidence, utcnow
from app.domain.project_lifecycle import CreateProject
from app.domain.project_sources import CreateProjectSource
from app.settings import Settings


class FixtureExecutor:
    """Contract fixture, deliberately not a PDF/CAD detector qualification."""

    name = "fixture-comparison"
    version = "pinned-test-1"

    def __init__(self, kind="pdf_comparison"):
        self.kind = kind
        self.calls = 0
        self.during = lambda context: None
        self.map_output = lambda context, draft: draft
        self.output = None

    def execute(self, context):
        self.calls += 1
        self.during(context)
        return (
            self.output
            if self.output is not None
            else json.dumps([hashlib.sha256(v).hexdigest() for v in context.originals]).encode()
        )

    def normalize(self, context, raw, artifact_key):
        bound = context.request
        target = (
            DrawingTarget(source_revision_id=bound.to_revision_id, page=1)
            if self.kind == "pdf_comparison"
            else CadTarget(source_revision_id=bound.to_revision_id, entity_id="native-entity")
        )
        draft = EngineeringPublication(
            operation_id="provider-does-not-own-this",
            changes=(
                Change(
                    id="provider-does-not-own-record-ids",
                    project_id=context.project_id,
                    source_id=bound.source_id,
                    from_revision_id=bound.from_revision_id,
                    to_revision_id=bound.to_revision_id,
                    subject=target,
                    kind="fixture-change",
                    detector=self.name,
                    detector_version=self.version,
                    raw_artifact_key=artifact_key,
                ),
            ),
            evidence=(
                Evidence(
                    id="provider-does-not-own-evidence-ids",
                    snapshot_id=context.snapshot.id,
                    provider=self.name,
                    source_id=bound.source_id,
                    source_revision_id=bound.to_revision_id,
                    source_revision=bound.revisions[1].sha256,
                    observed_at=utcnow(),
                    fact=raw.decode(),
                    viewer_target=target,
                ),
            ),
        )
        return self.map_output(context, draft)


def setup_pair(svc, admin, kind="pdf_comparison"):
    project = svc.projects.create(CreateProject(name="Trusted comparison"), admin)
    source = svc.sources.create(
        project.id, CreateProjectSource(name="Drawing", kind="DRAWING"), admin
    )
    extension = "pdf" if kind == "pdf_comparison" else "dxf"
    first = svc.sources.upload(
        project.id, source.id, "r1." + extension, b"original-r1", admin
    ).revision
    second = svc.sources.upload(
        project.id, source.id, "r2." + extension, b"original-r2", admin
    ).revision
    request = ComparisonRequest(
        kind=kind,
        operation_id="operation",
        source_id=source.id,
        from_revision_id=first.id,
        to_revision_id=second.id,
        options={"fixture": True},
    )
    executor = FixtureExecutor(kind)
    svc.comparisons.register(executor)
    return project, request, executor


def assert_no_output(svc, project_id):
    with svc.factory.open() as repo:
        assert repo.changes(project_id) == []
        assert repo.evidence(project_id) == []


@pytest.mark.parametrize("kind", ["pdf_comparison", "cad_comparison"])
def test_atomic_durable_job_originals_artifact_and_idempotent_replay(services, admin, kind):
    project, request, executor = setup_pair(services, admin, kind)
    observed = []
    executor.during = lambda context: observed.append(context)
    run = services.comparisons.submit(project.id, request, admin)
    assert run.status == "COMPLETED" and executor.calls == 1
    assert observed[0].originals == (b"original-r1", b"original-r2")
    with services.factory.open() as repo:
        job = repo.job(run.id)
        changes, evidence = repo.changes(project.id), repo.evidence(project.id)
        assert job.result["change_ids"] == [changes[0].id]
        assert job.result["evidence_ids"] == [evidence[0].id]
        assert changes[0].id != "provider-does-not-own-record-ids"
        assert changes[0].raw_artifact_key == job.result["artifact_key"]
        assert evidence[0].snapshot_id == job.snapshot_id
        snapshot = repo.snapshot(job.snapshot_id)
        assert evidence[0].observed_at == changes[0].created_at == snapshot.captured_at
        assert len(job.request.revisions) == 2
        assert repo.latest_baseline(project.id) is None
        assert repo.findings(project.id) == []
    assert (
        services.artifacts.read(job.result["artifact_key"])
        == json.dumps([r.sha256 for r in job.request.revisions]).encode()
    )
    assert services.comparisons.submit(project.id, request, admin).id == run.id
    assert executor.calls == 1


def test_successful_cache_reuse_and_options_version_isolation(services, admin):
    project, request, executor = setup_pair(services, admin)
    first = services.comparisons.submit(project.id, request, admin)
    second = services.comparisons.submit(
        project.id, request.model_copy(update={"operation_id": "two"}), admin
    )
    assert executor.calls == 1
    with services.factory.open() as repo:
        assert repo.job(second.id).result["cache_hit"]
        assert (
            repo.job(first.id).result["artifact_key"] == repo.job(second.id).result["artifact_key"]
        )
        assert repo.job(first.id).snapshot_id != repo.job(second.id).snapshot_id
    services.comparisons.submit(
        project.id,
        request.model_copy(update={"operation_id": "three", "options": {"different": True}}),
        admin,
    )
    executor.version = "pinned-test-2"
    services.comparisons.submit(
        project.id, request.model_copy(update={"operation_id": "four"}), admin
    )
    assert executor.calls == 3


@pytest.mark.parametrize("update", [{"options": {"different": True}}, {"kind": "cad_comparison"}])
def test_operation_identity_cannot_be_rebound(services, admin, update):
    project, request, executor = setup_pair(services, admin)
    services.comparisons.enqueue(project.id, request, admin)
    if "kind" in update:
        services.comparisons.register(FixtureExecutor("cad_comparison"))
    with pytest.raises((Conflict, DomainError)):
        services.comparisons.enqueue(project.id, request.model_copy(update=update), admin)
    assert executor.calls == 0


@pytest.mark.parametrize("mode", ["reverse", "same", "foreign", "obsolete", "format"])
def test_invalid_or_obsolete_pair_never_runs(services, admin, mode):
    project, request, executor = setup_pair(services, admin)
    if mode == "reverse":
        request = request.model_copy(
            update={
                "from_revision_id": request.to_revision_id,
                "to_revision_id": request.from_revision_id,
            }
        )
    elif mode == "same":
        request = request.model_copy(update={"from_revision_id": request.to_revision_id})
    elif mode == "foreign":
        project = services.projects.create(CreateProject(name="Other project"), admin)
    elif mode == "obsolete":
        services.sources.upload(project.id, request.source_id, "r3.pdf", b"r3", admin)
    else:
        request = request.model_copy(update={"kind": "cad_comparison"})
        services.comparisons.register(FixtureExecutor("cad_comparison"))
    with pytest.raises((Conflict, NotFound, DomainError)):
        services.comparisons.enqueue(project.id, request, admin)
    assert executor.calls == 0


@pytest.mark.parametrize("stage", ["before", "during"])
@pytest.mark.parametrize("side", [0, 1])
def test_both_originals_are_verified_before_and_after_execution(services, admin, stage, side):
    project, request, executor = setup_pair(services, admin)
    run = services.comparisons.enqueue(project.id, request, admin)
    with services.factory.open() as repo:
        revision = repo.job(run.id).request.revisions[side]

    def corrupt(context):
        return services.storage.put(revision.storage_key, b"corrupt")

    if stage == "before":
        corrupt(None)
    else:
        executor.during = corrupt
    with pytest.raises(Conflict, match="verification"):
        services.comparisons.process(run.id, generation=0)
    assert_no_output(services, project.id)


@pytest.mark.parametrize("mode", ["cancel", "expire", "generation", "new-revision"])
def test_inflight_fences_prevent_publication_and_cache_authority(services, admin, mode):
    project, request, executor = setup_pair(services, admin)
    run = services.comparisons.enqueue(project.id, request, admin)

    def invalidate(context):
        if mode == "cancel":
            services.coordination.cancel(run.id, admin)
        elif mode == "expire":
            services.coordination.expire(run.id)
        elif mode == "new-revision":
            services.sources.upload(project.id, request.source_id, "r3.pdf", b"r3", admin)
        else:
            with services.factory.open(project.id, write=True) as repo:
                repo.save_run(
                    repo.run(run.id).model_copy(update={"generation": 1, "status": "QUEUED"})
                )

    executor.during = invalidate
    if mode == "new-revision":
        with pytest.raises(Conflict, match="obsolete"):
            services.comparisons.process(run.id, generation=0)
    else:
        assert services.comparisons.process(run.id, generation=0) != "COMPLETED"
    assert_no_output(services, project.id)
    with services.factory.open() as repo:
        assert repo.publication_digest(project.id, run.id) is None
        assert repo.job(run.id).result is None
    if mode == "cancel":
        # Cancelled staged output has no successful marker and cannot feed another job.
        executor.during = lambda context: None
        services.comparisons.submit(
            project.id, request.model_copy(update={"operation_id": "next"}), admin
        )
        assert executor.calls == 2


@pytest.mark.parametrize("mode", ["pair", "project", "artifact", "engine", "target", "evidence"])
def test_mapper_cannot_escape_execution_binding(services, admin, mode):
    project, request, executor = setup_pair(services, admin)

    def invalid(context, draft):
        if mode == "evidence":
            return draft.model_copy(
                update={
                    "evidence": (
                        draft.evidence[0].model_copy(update={"source_revision": "0" * 64}),
                    )
                }
            )
        updates = {
            "pair": {"from_revision_id": request.to_revision_id},
            "project": {"project_id": "another-project"},
            "artifact": {"raw_artifact_key": "invented"},
            "engine": {"detector_version": "another-version"},
            "target": {"subject": CadTarget(source_revision_id=request.to_revision_id)},
        }[mode]
        return draft.model_copy(update={"changes": (draft.changes[0].model_copy(update=updates),)})

    executor.map_output = invalid
    run = services.comparisons.enqueue(project.id, request, admin)
    with pytest.raises(Conflict):
        services.comparisons.process(run.id, generation=0)
    assert_no_output(services, project.id)


@pytest.mark.parametrize(
    "output",
    [b"", b"x" * (8 * 1024 * 1024 + 1), "browser-result"],
    ids=["empty", "oversized", "wrong-type"],
)
def test_empty_oversized_or_wrong_output_is_rejected(services, admin, output):
    project, request, executor = setup_pair(services, admin)
    executor.output = output
    run = services.comparisons.enqueue(project.id, request, admin)
    with pytest.raises(DomainError, match="worker output"):
        services.comparisons.process(run.id, generation=0)
    assert_no_output(services, project.id)


def test_retry_recovers_original_binding_and_rolls_back_partial_publication(
    services, admin, monkeypatch
):
    from app.adapters.persistence.repository import SQLCoordinationRepository

    project, request, executor = setup_pair(services, admin)
    run = services.comparisons.enqueue(project.id, request, admin)
    original = SQLCoordinationRepository.save_job

    def fail_completion(repo, job):
        if job.result:
            raise RuntimeError("fault between publication and completion")
        return original(repo, job)

    with monkeypatch.context() as patch:
        patch.setattr(SQLCoordinationRepository, "save_job", fail_completion)
        with pytest.raises(RuntimeError, match="fault"):
            services.comparisons.process(run.id, generation=0)
    assert_no_output(services, project.id)
    with services.factory.open() as repo:
        snapshot_id = repo.job(run.id).snapshot_id
    assert services.comparisons.process(run.id, generation=0) == "COMPLETED"
    with services.factory.open() as repo:
        assert repo.job(run.id).snapshot_id == snapshot_id
    assert executor.calls == 2


def test_missing_or_changed_pinned_executor_is_explicit(services, admin):
    project, request, executor = setup_pair(services, admin)
    run = services.comparisons.enqueue(project.id, request, admin)
    executor.version = "different"
    with pytest.raises(CapabilityUnavailable, match="version"):
        services.comparisons.process(run.id, generation=0)
    assert executor.calls == 0


def test_api_accepts_only_requests_and_rejects_raw_browser_records(services, client, admin):
    project, request, executor = setup_pair(services, admin)
    url = f"/api/projects/{project.id}/engineering/comparisons"
    response = client.post(url, json={**request.model_dump(), "changes": []})
    assert response.status_code == 422
    response = client.post(url, json=request.model_dump())
    assert response.status_code == 202 and response.json()["status"] == "COMPLETED"
    assert executor.calls == 1
    services.comparisons.executors.clear()
    assert client.post(url, json=request.model_dump()).status_code == 503
    rows = {row["name"]: row for row in client.get("/api/capabilities").json()["capabilities"]}
    assert rows["Trusted PDF comparison"]["status"] == "unavailable_dependency"
    assert rows["Trusted PDF comparison"]["service_reachable"] is None
    with pytest.raises(PermissionDenied):
        services.comparisons.enqueue(project.id, request, Principal(id="reader", role="viewer"))


def test_registered_executors_are_available_before_queued_recovery(tmp_path, admin, monkeypatch):
    from app.adapters.runtime_diagnostic import DiagnosticRuntime

    settings = Settings(data_dir=tmp_path, diagnostic_runtime=True, seed_demo=False)
    svc = build_services(settings)
    try:
        project, request, executor = setup_pair(svc, admin)
        run = svc.comparisons.enqueue(project.id, request, admin)
    finally:
        svc.close()
    observed = []
    original = DiagnosticRuntime.start

    def recover(runtime, identity):
        assert runtime.coordinator.inner.comparisons.executors[executor.kind] is executor
        observed.append(identity)
        return original(runtime, identity)

    monkeypatch.setattr(DiagnosticRuntime, "start", recover)
    restored = build_services(settings, comparison_executors=(executor,))
    try:
        assert observed == [run.id]
        with restored.factory.open() as repo:
            assert repo.run(run.id).status == "COMPLETED"
    finally:
        restored.close()


@pytest.mark.parametrize("mode", ["options", "artifact"])
def test_worker_cannot_mutate_binding_or_retained_bytes(services, admin, mode):
    project, request, executor = setup_pair(services, admin)

    def mutate(context, draft):
        if mode == "options":
            context.request.options["fixture"] = False
        else:
            services.storage.put(draft.changes[0].raw_artifact_key, b"invalid-envelope")
        return draft

    executor.map_output = mutate
    run = services.comparisons.enqueue(project.id, request, admin)
    with pytest.raises(Conflict):
        services.comparisons.process(run.id, generation=0)
    assert_no_output(services, project.id)


def test_corrupt_completed_cache_never_becomes_new_facts(services, admin):
    project, request, executor = setup_pair(services, admin)
    run = services.comparisons.submit(project.id, request, admin)
    with services.factory.open() as repo:
        key = repo.job(run.id).result["artifact_key"]
    services.storage.put(key, b"invalid-envelope")
    next_run = services.comparisons.enqueue(
        project.id, request.model_copy(update={"operation_id": "two"}), admin
    )
    with pytest.raises(Conflict, match="integrity"):
        services.comparisons.process(next_run.id, generation=0)
    assert executor.calls == 1
    with services.factory.open() as repo:
        assert len(repo.changes(project.id)) == 1
        assert repo.job(next_run.id).result is None


def test_unchanged_result_retains_verified_artifact_and_input_pair(services, admin):
    project, request, executor = setup_pair(services, admin)
    executor.map_output = lambda context, draft: draft.model_copy(
        update={"changes": (), "evidence": ()}
    )
    run = services.comparisons.submit(project.id, request, admin)
    with services.factory.open() as repo:
        job = repo.job(run.id)
        assert job.result["change_ids"] == []
        assert job.result["evidence_ids"] == []
        assert len(job.request.revisions) == 2
        assert repo.publication_digest(project.id, run.id)
    assert services.artifacts.read(job.result["artifact_key"]) is not None
