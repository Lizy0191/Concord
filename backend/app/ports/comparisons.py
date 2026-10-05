"""Trusted deployment injection; no client-selected program or browser result."""

from dataclasses import dataclass
from typing import Protocol

from app.domain.comparisons import BoundComparison
from app.domain.engineering import EngineeringPublication
from app.domain.models import ProjectSnapshot


@dataclass(frozen=True)
class ComparisonExecution:
    project_id: str
    run_id: str
    generation: int
    request: BoundComparison
    snapshot: ProjectSnapshot
    originals: tuple[bytes, bytes]


class ComparisonExecutor(Protocol):
    kind: str
    name: str
    version: str

    def execute(self, context: ComparisonExecution) -> bytes:
        """Run the pinned engine on verified originals; return bounded raw output."""
        ...

    def normalize(
        self, context: ComparisonExecution, raw: bytes, artifact_key: str
    ) -> EngineeringPublication:
        """Map retained engine output to the existing canonical contracts."""
        ...
