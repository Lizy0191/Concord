"""Durable trusted comparisons using existing jobs, outbox and publication records."""

import hashlib
from uuid import NAMESPACE_URL, uuid5

from app.application.comparison_inputs import (
    bind_comparison,
    comparison_digest,
    read_originals,
    validate_current,
)
from app.application.comparison_publication import output_key, retain_output, validate_publication
from app.application.derived_artifacts import DerivedArtifacts
from app.application.engineering_publication import publish
from app.application.streaming import custom, emit
from app.domain.actions import AuditRecord, Principal
from app.domain.comparisons import BoundComparison, ComparisonRequest
from app.domain.errors import CapabilityUnavailable, Conflict, NotFound
from app.domain.jobs import CapabilityJob
from app.domain.models import ProjectSnapshot, utcnow
from app.domain.runs import AgentRun, Capability
from app.policies.actions import require
from app.ports.comparisons import ComparisonExecution, ComparisonExecutor
from app.ports.coordination import RepositoryFactory
from app.ports.services import DurableRuntime, FileStore


class ComparisonService:
    def __init__(
        self,
        factory: RepositoryFactory,
        storage: FileStore,
        artifacts: DerivedArtifacts,
        runtime_name: str,
    ):
        self.factory, self.storage, self.artifacts = factory, storage, artifacts
        self.runtime_name = runtime_name
        self.runtime: DurableRuntime | None = None
        self.executors: dict[str, ComparisonExecutor] = {}

    def register(self, executor: ComparisonExecutor) -> None:
        if (
            executor.kind not in {"pdf_comparison", "cad_comparison"}
            or executor.kind in self.executors
            or not executor.name
            or not executor.version
        ):
            raise Conflict("Comparison executor needs a unique supported kind and pinned identity")
        self.executors[executor.kind] = executor

    def enqueue(
        self, project_id: str, request: ComparisonRequest, principal: Principal
    ) -> AgentRun:
        require(principal, "ingest")
        executor = self._executor(request.kind)
        identity = str(
            uuid5(NAMESPACE_URL, f"concord:comparison:{project_id}:{request.operation_id}")
        )
        with self.factory.open(project_id, write=True) as repo:
            repo.state(project_id)
            bound = bind_comparison(repo, project_id, request, executor)
            try:
                previous = repo.job(identity)
            except NotFound:
                previous = None
            if previous is not None:
                if previous.project_id != project_id or previous.request != bound:
                    raise Conflict("Comparison operation is already bound to different inputs")
                return repo.run(identity)
            run = AgentRun(
                id=identity, project_id=project_id, category=request.kind, runtime=self.runtime_name
            )
            repo.save_run(run)
            repo.save_job(
                CapabilityJob(
                    id=identity, project_id=project_id, requested_by=principal.id, request=bound
                )
            )
            emit(repo, identity, "RUN_STARTED")
            repo.audit(
                AuditRecord(
                    project_id=project_id,
                    actor=principal.id,
                    action="COMPARISON_REQUESTED",
                    run_id=identity,
                    detail={"binding": comparison_digest(project_id, bound)},
                )
            )
        return run

    def submit(self, project_id: str, request: ComparisonRequest, principal: Principal) -> AgentRun:
        if self.runtime is None:
            raise CapabilityUnavailable("Comparison runtime is not initialized")
        run = self.enqueue(project_id, request, principal)
        if run.status == "QUEUED":
            if run.generation:
                self.runtime.resume(run.id)
            else:
                self.runtime.start(run.id)
        with self.factory.open() as repo:
            return repo.run(run.id)

    def _executor(self, kind: str, version: str | None = None) -> ComparisonExecutor:
        executor = self.executors.get(kind)
        if executor is None:
            raise CapabilityUnavailable("No trusted comparison executor is registered for " + kind)
        if version is not None and executor.version != version:
            raise CapabilityUnavailable("Pinned comparison executor version is unavailable")
        return executor

    def capability_status(self) -> list[Capability]:
        rows = []
        for kind, name in (
            ("pdf_comparison", "Trusted PDF comparison"),
            ("cad_comparison", "Trusted CAD comparison"),
        ):
            executor = self.executors.get(kind)
            rows.append(
                Capability(
                    name=name,
                    implementation=executor.name if executor else "ComparisonExecutor",
                    status="enabled" if executor else "unavailable_dependency",
                    enabled=executor is not None,
                    dependency_available=executor is not None,
                    version=executor.version if executor else None,
                    reason="Trusted executor registered; SDK execution health is not probed"
                    if executor
                    else (
                        "No trusted comparison executor is registered; "
                        "browser results cannot be published"
                    ),
                )
            )
        return rows

    def process(self, run_id: str, *, generation: int) -> str:
        with self.factory.open() as repo:
            job = repo.job(run_id)
        bound = job.request
        if not isinstance(bound, BoundComparison):
            raise Conflict("Comparison worker received another job type")
        binding = comparison_digest(job.project_id, bound)
        with self.factory.open(job.project_id, write=True) as repo:
            run = repo.run(run_id)
            if run.generation != generation or run.status in {"CANCELLED", "EXPIRED", "COMPLETED"}:
                return run.status
            validate_current(repo, job.project_id, bound)
            # Reuse the persisted observation/identity on a retry or process recovery.
            current_job = repo.job(run_id)
            if current_job.snapshot_id:
                snapshot = repo.snapshot(current_job.snapshot_id)
            else:
                state = repo.state(job.project_id)
                snapshot = ProjectSnapshot(
                    project_id=job.project_id, version=state.version, sources=state.sources
                )
                repo.save_snapshot(snapshot)
                repo.save_job(job.model_copy(update={"snapshot_id": snapshot.id}))
            repo.save_run(run.model_copy(update={"status": "RUNNING", "updated_at": utcnow()}))
            emit(repo, run_id, "STEP_STARTED", stepName=bound.kind)
        executor = self._executor(bound.kind, bound.engine_version)
        if executor.name != bound.engine:
            raise CapabilityUnavailable("Pinned comparison executor identity is unavailable")
        context = ComparisonExecution(
            job.project_id, run_id, generation, bound, snapshot, read_originals(self.storage, bound)
        )
        recipe = bound.model_copy(update={"operation_id": "cache"})
        cache_id = "comparison-cache:" + comparison_digest(job.project_id, recipe)
        with self.factory.open() as repo:
            # Only an atomic successful publication can authorize cache reuse.
            cached_digest = repo.publication_digest(job.project_id, cache_id)
        raw = (
            self.artifacts.read(output_key(self.artifacts, context, cached_digest))
            if cached_digest
            else None
        )
        cached = raw is not None
        if raw is None:
            raw = executor.execute(context)
        elif hashlib.sha256(raw).hexdigest() != cached_digest:
            raise Conflict("Comparison cache failed its trusted publication digest")
        artifact_key = retain_output(self.artifacts, context, raw)
        draft = validate_publication(
            context, executor.normalize(context, raw, artifact_key), artifact_key
        )
        if comparison_digest(job.project_id, bound) != binding:
            raise Conflict("Comparison executor mutated the immutable input binding")
        if self.artifacts.read(artifact_key) != raw:
            raise Conflict("Comparison artifact changed during normalization")
        # Reverify originals after slow work, outside the project write transaction.
        read_originals(self.storage, bound)
        with self.factory.open(job.project_id, write=True) as repo:
            current = repo.run(run_id)
            if current.generation != generation or current.status in {
                "CANCELLED",
                "EXPIRED",
                "COMPLETED",
            }:
                return current.status
            validate_current(repo, job.project_id, bound)
            if repo.job(run_id).request != bound:
                raise Conflict("Persisted comparison binding changed during execution")
            publish(repo, job.project_id, draft)
            digest = hashlib.sha256(raw).hexdigest()
            previous_cache = repo.publication_digest(job.project_id, cache_id)
            if previous_cache is not None and previous_cache != digest:
                raise Conflict("Pinned comparison produced inconsistent output for the same inputs")
            if previous_cache is None:
                repo.add_publication(job.project_id, cache_id, digest)
            result = {
                "artifact_key": artifact_key,
                "artifact_sha256": digest,
                "change_ids": [c.id for c in draft.changes],
                "evidence_ids": [e.id for e in draft.evidence],
                "binding": comparison_digest(job.project_id, bound),
                "cache_hit": cached,
                "snapshot_id": snapshot.id,
            }
            repo.save_job(repo.job(run_id).model_copy(update={"result": result}))
            repo.save_run(
                current.model_copy(
                    update={"status": "COMPLETED", "error": None, "updated_at": utcnow()}
                )
            )
            emit(repo, run_id, "STEP_FINISHED", stepName=bound.kind)
            custom(repo, run_id, "capability-result", {"job_id": run_id, "capability": bound.kind})
            repo.audit(
                AuditRecord(
                    project_id=job.project_id,
                    actor="comparison-worker",
                    action="COMPARISON_PUBLISHED",
                    run_id=run_id,
                    detail={
                        "binding": result["binding"],
                        "artifact_key": artifact_key,
                        "artifact_sha256": digest,
                        "cache_hit": cached,
                        "change_count": len(draft.changes),
                        "evidence_count": len(draft.evidence),
                    },
                )
            )
        return "COMPLETED"
