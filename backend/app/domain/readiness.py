"""Deterministic constraints. Text/model output cannot change these numeric rules."""

from app.domain.models import (
    Constraint,
    ConstraintKind,
    Evidence,
    Finding,
    Impact,
    ProjectSnapshot,
    ProjectState,
    Readiness,
)


def evaluate(
    state: ProjectState, snapshot: ProjectSnapshot
) -> tuple[
    tuple[Evidence, ...], tuple[Finding, ...], tuple[Constraint, ...], tuple[Readiness, ...], Impact
]:
    evidence: list[Evidence] = []
    findings: list[Finding] = []
    constraints: list[Constraint] = []
    statuses: list[Readiness] = []
    affected = []
    for wp in state.work_packages:
        issues: list[tuple[ConstraintKind, str, str, str | None]] = []
        if wp.design_revision != wp.accepted_revision:
            issues.append(
                (
                    "design",
                    "drawing",
                    f"Drawing {wp.design_revision} is current; "
                    f"workface acknowledged {wp.accepted_revision}.",
                    None,
                )
            )
        for predecessor in wp.predecessors:
            if not state.package(predecessor).complete:
                issues.append(
                    (
                        "predecessor",
                        "schedule",
                        f"Predecessor {predecessor} is incomplete.",
                        predecessor,
                    )
                )
        if wp.available_workers < wp.required_workers:
            issues.append(
                (
                    "workforce",
                    "workforce",
                    f"Crew available {wp.available_workers}; required {wp.required_workers}.",
                    None,
                )
            )
        missing = sorted(set(wp.required_qualifications) - set(wp.qualifications))
        if missing:
            issues.append(
                (
                    "qualification",
                    "workforce",
                    f"Missing qualifications: {', '.join(missing)}.",
                    None,
                )
            )
        for name, available in wp.materials.items():
            if not available:
                issues.append(("material", "material", f"Material {name} is unavailable.", name))
        for name, available in wp.equipment.items():
            if not available:
                issues.append(("equipment", "equipment", f"Equipment {name} is unavailable.", name))
        if not wp.inspection_passed:
            issues.append(
                ("inspection", "inspection", "Inspection acceptance has not passed.", None)
            )
        package_constraints = []
        for kind, source, fact, resource in issues:
            revision = state.source(source)
            item = Evidence(
                snapshot_id=snapshot.id,
                provider=f"structured-{source}",
                source_id=f"{source}/{wp.id}",
                source_revision=revision.revision,
                observed_at=revision.observed_at,
                work_package_id=wp.id,
                element_ids=wp.element_ids,
                location=wp.area_id,
                fact=fact,
            )
            evidence.append(item)
            constraint = Constraint(
                snapshot_id=snapshot.id,
                work_package_id=wp.id,
                kind=kind,
                description=fact,
                evidence_ids=(item.id,),
                resource_id=resource,
            )
            constraints.append(constraint)
            package_constraints.append(constraint.id)
            findings.append(
                Finding(
                    snapshot_id=snapshot.id,
                    work_package_id=wp.id,
                    conclusion=fact,
                    evidence_ids=(item.id,),
                    reasoning_summary=f"Deterministic {kind} rule compared recorded project facts.",
                    limitations=("Synthetic provider state; not a final safety judgment.",),
                )
            )
        if issues:
            affected.append(wp)
        statuses.append(
            Readiness(
                work_package_id=wp.id,
                status="BLOCKED" if issues else "READY",
                constraint_ids=tuple(package_constraints),
                snapshot_id=snapshot.id,
            )
        )
    impact = Impact(
        work_package_ids=tuple(wp.id for wp in affected),
        area_ids=tuple(sorted({wp.area_id for wp in affected})),
        element_ids=tuple(sorted({element for wp in affected for element in wp.element_ids})),
        disciplines=tuple(sorted({wp.discipline for wp in affected})),
    )
    return tuple(evidence), tuple(findings), tuple(constraints), tuple(statuses), impact
