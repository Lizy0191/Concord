"""Deterministic V16 to V17 engineering data for the primary demo scenario."""

from datetime import UTC, datetime

from app.adapters.demo import demo_state
from app.domain.errors import DomainError
from app.domain.models import ProjectState

FIXTURE_OBSERVED_AT = datetime(2026, 9, 13, 8, 0, tzinfo=UTC)


def design_change_state(revision: str = "V17") -> ProjectState:
    """Return the traceable V16 baseline or V17 changed project state."""
    if revision not in {"V16", "V17"}:
        raise DomainError("Design-change fixture supports only V16 or V17")
    state = demo_state()
    sources = tuple(
        source.model_copy(
            update={
                "revision": revision if source.source in {"drawing", "bim"} else "r1",
                "observed_at": FIXTURE_OBSERVED_AT,
            }
        )
        for source in state.sources
    )
    packages = tuple(
        package.model_copy(update={"design_revision": revision})
        if package.id == "WP-200"
        else package
        for package in state.work_packages
    )
    return state.model_copy(
        update={
            "version": 2 if revision == "V17" else 1,
            "sources": sources,
            "work_packages": packages,
        }
    )
