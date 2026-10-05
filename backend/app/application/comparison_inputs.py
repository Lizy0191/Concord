"""Bind and revalidate both ordered originals using authoritative source records."""

import hashlib
import json
from pathlib import PurePath

from app.domain.comparisons import BoundComparison, ComparisonRequest
from app.domain.errors import Conflict, DomainError
from app.ports.comparisons import ComparisonExecutor
from app.ports.coordination import CoordinationRepository
from app.ports.services import FileStore


def bind_comparison(
    repo: CoordinationRepository,
    project_id: str,
    request: ComparisonRequest,
    executor: ComparisonExecutor,
) -> BoundComparison:
    source = repo.project_source(project_id, request.source_id)
    revisions = (
        repo.source_revision(project_id, source.id, request.from_revision_id),
        repo.source_revision(project_id, source.id, request.to_revision_id),
    )
    suffix = ".pdf" if request.kind == "pdf_comparison" else ".dxf"
    if source.kind != "DRAWING" or any(
        PurePath(r.original_filename).suffix.lower() != suffix for r in revisions
    ):
        raise DomainError("Comparison requires two Drawing originals of the selected format")
    if revisions[0].sequence >= revisions[1].sequence:
        raise Conflict("Comparison revisions must be distinct and ordered oldest to newest")
    bound = BoundComparison(
        **request.model_dump(),
        engine=executor.name,
        engine_version=executor.version,
        revisions=revisions,
    )
    validate_current(repo, project_id, bound)
    return bound


def validate_current(repo: CoordinationRepository, project_id: str, bound: BoundComparison) -> None:
    for revision in bound.revisions:
        if repo.source_revision(project_id, bound.source_id, revision.id) != revision:
            raise Conflict("Comparison original identity changed")
    latest = repo.latest_source_revision(project_id, bound.source_id)
    if latest is None or latest.id != bound.to_revision_id:
        raise Conflict("Comparison became obsolete after a newer source revision")


def read_originals(storage: FileStore, bound: BoundComparison) -> tuple[bytes, bytes]:
    values = []
    for revision in bound.revisions:
        content = storage.read(revision.storage_key)
        if (
            len(content) != revision.size_bytes
            or hashlib.sha256(content).hexdigest() != revision.sha256
        ):
            raise Conflict("Comparison original failed size/hash verification")
        values.append(content)
    return values[0], values[1]


def comparison_digest(project_id: str, bound: BoundComparison) -> str:
    return hashlib.sha256(
        json.dumps([project_id, bound.model_dump(mode="json")], sort_keys=True).encode()
    ).hexdigest()
