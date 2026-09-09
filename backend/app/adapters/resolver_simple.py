from app.domain.actions import Effect, ResolutionOption
from app.domain.models import Constraint, ProjectState


class SimpleResolver:
    def resolve(
        self, state: ProjectState, constraints: tuple[Constraint, ...]
    ) -> list[ResolutionOption]:
        options = []
        for wp in state.work_packages:
            relevant = [item for item in constraints if item.work_package_id == wp.id]
            if not relevant:
                continue
            effects = []
            for item in relevant:
                kind, value = {
                    "design": ("acknowledge_design", wp.design_revision),
                    "workforce": ("assign_crew", wp.required_workers),
                    "qualification": ("confirm_qualification", wp.required_qualifications),
                    "predecessor": ("confirm_predecessor", True),
                    "material": ("confirm_material", True),
                    "equipment": ("confirm_equipment", True),
                    "inspection": ("record_inspection", True),
                }[item.kind]
                effects.append(
                    Effect(
                        kind=kind, value=value, work_package_id=wp.id, resource_id=item.resource_id
                    )
                )
            options.append(
                ResolutionOption(
                    title=f"Coordinate {wp.name}",
                    explanation=(
                        "Obtain the listed confirmations from responsible owners, "
                        "then refresh and re-check. "
                        "Demo execution simulates confirmations; it does not perform "
                        "site work or certify safety."
                    ),
                    constraint_ids=tuple(item.id for item in relevant),
                    effects=tuple(effects),
                )
            )
        return options
