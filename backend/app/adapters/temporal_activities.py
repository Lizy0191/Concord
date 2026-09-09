from temporalio import activity

from app.ports.services import WorkflowDriver


class CoordinationActivities:
    def __init__(self, coordinator: WorkflowDriver):
        self.coordinator = coordinator

    @activity.defn(name="cca-analyze")
    def analyze(self, run_id: str, generation: int = 0) -> str:
        return self.coordinator.begin(run_id, generation=generation)

    @activity.defn(name="cca-advance")
    def advance(self, run_id: str, message: dict, generation: int = 0) -> str:
        return self.coordinator.advance(run_id, message, generation=generation)

    @activity.defn(name="cca-expire")
    def expire(self, run_id: str, generation: int = 0) -> str:
        return self.coordinator.expire(run_id, generation=generation)
