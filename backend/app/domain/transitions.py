"""Validated external observations and simulated confirmations share versioned state transitions."""

from app.domain.actions import Effect
from app.domain.errors import DomainError
from app.domain.events import ProjectEvent
from app.domain.models import ProjectState, SourceRevision, WorkPackage, utcnow


def revise(
    state: ProjectState, packages: tuple[WorkPackage, ...], sources: set[str]
) -> ProjectState:
    version = state.version + 1
    revisions = tuple(
        SourceRevision(source=s.source, revision=f"r{version}", observed_at=utcnow())
        if s.source in sources
        else s
        for s in state.sources
    )
    return state.model_copy(
        update={"version": version, "work_packages": packages, "sources": revisions}
    )


def apply_event(state: ProjectState, event: ProjectEvent) -> ProjectState:
    wp = state.package(event.work_package_id)
    change = event.change
    source = "schedule"
    fields: dict = {}
    target_id = wp.id
    if event.kind == "design_revision":
        source, fields = "drawing", {"design_revision": change.revision}
    elif event.kind == "workforce":
        source, fields = "workforce", {"available_workers": change.available_workers}
        if change.qualifications is not None:
            fields["qualifications"] = change.qualifications
    elif event.kind == "predecessor":
        if change.predecessor_id not in wp.predecessors:
            raise DomainError("Event predecessor is not a dependency of the target work package")
        target_id, fields = str(change.predecessor_id), {"complete": change.complete}
    elif event.kind in {"material", "equipment"}:
        source = event.kind
        key = "materials" if event.kind == "material" else "equipment"
        resources = dict(getattr(wp, key))
        if change.resource_id not in resources:
            raise DomainError("Unknown resource for this work package")
        resources[str(change.resource_id)] = change.available
        fields = {key: resources}
    elif event.kind == "inspection":
        source, fields = "inspection", {"inspection_passed": change.inspection_passed}
    packages = tuple(
        WorkPackage.model_validate({**p.model_dump(), **fields}) if p.id == target_id else p
        for p in state.work_packages
    )
    return revise(state, packages, {source})


def apply_effects(state: ProjectState, effects: tuple[Effect, ...]) -> ProjectState:
    packages = {p.id: p for p in state.work_packages}
    sources: set[str] = set()
    for effect in effects:
        wp = packages[effect.work_package_id]
        fields: dict = {}
        source = "schedule"
        if effect.kind == "acknowledge_design":
            if effect.value != wp.design_revision:
                raise DomainError("Cannot acknowledge a revision other than the current drawing")
            fields, source = {"accepted_revision": effect.value}, "drawing"
        elif effect.kind == "assign_crew":
            fields, source = {"available_workers": effect.value}, "workforce"
        elif effect.kind == "confirm_qualification":
            fields, source = {"qualifications": effect.value}, "workforce"
        elif effect.kind == "confirm_predecessor":
            if effect.resource_id not in wp.predecessors:
                raise DomainError("Cannot confirm an unrelated predecessor")
            predecessor = packages[str(effect.resource_id)]
            packages[predecessor.id] = predecessor.model_copy(update={"complete": True})
        elif effect.kind in {"confirm_material", "confirm_equipment"}:
            source = "material" if effect.kind == "confirm_material" else "equipment"
            key = "materials" if source == "material" else "equipment"
            resources = dict(getattr(wp, key))
            if effect.resource_id not in resources:
                raise DomainError("Cannot confirm an unrelated resource")
            resources[str(effect.resource_id)] = True
            fields = {key: resources}
        elif effect.kind == "record_inspection":
            fields, source = {"inspection_passed": True}, "inspection"
        packages[wp.id] = WorkPackage.model_validate({**wp.model_dump(), **fields})
        sources.add(source)
    return revise(state, tuple(packages[p.id] for p in state.work_packages), sources)
