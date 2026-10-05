"""Retain raw output and validate every normalized draft before atomic publication."""

import hashlib
from uuid import NAMESPACE_URL, uuid5

from app.application.derived_artifacts import DerivedArtifacts
from app.domain.engineering import EngineeringPublication
from app.domain.errors import Conflict, DomainError
from app.ports.comparisons import ComparisonExecution

MAX_RESULT_BYTES = 8 * 1024 * 1024


def output_key(artifacts: DerivedArtifacts, context: ComparisonExecution, digest: str) -> str:
    bound = context.request
    return artifacts.key(
        bound.engine,
        bound.engine_version,
        tuple(r.sha256 for r in bound.revisions),
        {
            "project_id": context.project_id,
            "source_id": bound.source_id,
            "revisions": [r.id for r in bound.revisions],
            "options": bound.options,
            "payload_sha256": digest,
        },
    )


def retain_output(artifacts: DerivedArtifacts, context: ComparisonExecution, raw: bytes) -> str:
    if not isinstance(raw, bytes) or not raw or len(raw) > MAX_RESULT_BYTES:
        raise DomainError("Comparison worker output must be nonempty bytes within 8 MiB")
    # Include payload hash: reruns can never overwrite a different retained result.
    key = output_key(artifacts, context, hashlib.sha256(raw).hexdigest())
    previous = artifacts.read(key)
    if previous is not None and previous != raw:
        raise Conflict("Immutable comparison artifact has different content")
    if previous is None:
        artifacts.write(key, raw)
    if artifacts.read(key) != raw:
        raise Conflict("Retained comparison artifact failed readback")
    return key


def validate_publication(
    context: ComparisonExecution, draft: EngineeringPublication, artifact_key: str
) -> EngineeringPublication:
    # Validate even a provider's model_copy output; copied updates bypass Pydantic validation.
    draft = EngineeringPublication.model_validate(draft.model_dump())
    bound = context.request
    revisions = {r.id: r for r in bound.revisions}
    target_kind = "drawing" if bound.kind == "pdf_comparison" else "cad"
    for change in draft.changes:
        if (
            change.project_id != context.project_id
            or change.source_id != bound.source_id
            or change.from_revision_id != bound.from_revision_id
            or change.to_revision_id != bound.to_revision_id
            or change.detector != bound.engine
            or change.detector_version != bound.engine_version
            or change.raw_artifact_key != artifact_key
            or change.subject.source_revision_id not in revisions
            or change.subject.kind != target_kind
        ):
            raise Conflict("Comparison Change does not match the trusted execution")
    for item in draft.evidence:
        revision = revisions.get(item.source_revision_id or "")
        if (
            revision is None
            or item.source_id != bound.source_id
            or item.source_revision != revision.sha256
            or item.snapshot_id != context.snapshot.id
            or item.viewer_target is None
            or item.viewer_target.source_revision_id != revision.id
            or item.viewer_target.kind != target_kind
        ):
            raise Conflict("Comparison Evidence does not match the trusted execution")
    # Platform owns identity and observation time, including after recovery.
    return draft.model_copy(
        update={
            "operation_id": context.run_id,
            "changes": tuple(
                item.model_copy(
                    update={
                        "id": str(uuid5(NAMESPACE_URL, f"{context.run_id}:change:{index}")),
                        "created_at": context.snapshot.captured_at,
                    }
                )
                for index, item in enumerate(draft.changes)
            ),
            "evidence": tuple(
                item.model_copy(
                    update={
                        "id": str(uuid5(NAMESPACE_URL, f"{context.run_id}:evidence:{index}")),
                        "observed_at": context.snapshot.captured_at,
                    }
                )
                for index, item in enumerate(draft.evidence)
            ),
        }
    )
