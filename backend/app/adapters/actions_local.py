from app.domain.actions import Effect
from app.domain.models import ProjectState
from app.domain.transitions import apply_effects


class SimulatedActionExecutor:
    mode = "simulated"

    def apply(
        self, state: ProjectState, effects: tuple[Effect, ...], operation_id: str
    ) -> ProjectState:
        return apply_effects(state, effects)

    def verify(
        self, before: ProjectState, after: ProjectState, effects: tuple[Effect, ...]
    ) -> bool:
        expected = apply_effects(before, effects)
        return after.work_packages == expected.work_packages and after.version == before.version + 1
