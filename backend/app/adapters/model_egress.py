"""Allowlisted model context. Raw workforce/personnel records never leave this boundary."""

import re
from dataclasses import dataclass

from app.domain.models import Evidence, ProjectSnapshot, ProjectState

REDACTIONS = (
    (re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}"), "[EMAIL]"),
    (re.compile(r"(?<!\w)\+?\d[\d ()-]{8,}\d(?!\w)"), "[PERSONAL_NUMBER]"),
    (re.compile(r"(?<!\w)\d{17}[0-9Xx](?!\w)"), "[GOVERNMENT_ID]"),
)


def sanitize(text: str, limit: int = 800) -> str:
    for pattern, replacement in REDACTIONS:
        text = pattern.sub(replacement, text)
    return text[:limit]


@dataclass(frozen=True)
class ReasoningContext:
    payload: dict


def minimize(
    state: ProjectState, snapshot: ProjectSnapshot, evidence: tuple[Evidence, ...]
) -> ReasoningContext:
    selected = evidence[:30]
    package_ids = {item.work_package_id for item in selected}
    packages = [p for p in state.work_packages if p.id in package_ids][:20]
    return ReasoningContext(
        {
            "snapshot_id": snapshot.id,
            "source_revisions": [
                {"source": s.source, "revision": sanitize(s.revision, 100)}
                for s in snapshot.sources
            ],
            "work_packages": [
                {
                    "id": p.id,
                    "discipline": sanitize(p.discipline, 80),
                    "predecessors": p.predecessors,
                    "required_workers": p.required_workers,
                    "available_workers": p.available_workers,
                }
                for p in packages
            ],
            "evidence": [
                {
                    "id": e.id,
                    "source_id": sanitize(e.source_id, 160),
                    "source_revision": sanitize(e.source_revision, 100),
                    "fact": sanitize(e.fact),
                }
                for e in selected
            ],
            "excluded": [
                "names",
                "phone_numbers",
                "government_ids",
                "biometrics",
                "trajectories",
                "raw_documents",
                "event_notes",
            ],
        }
    )
