"""Project-owned scheduling input/output; solver types never cross this boundary."""

from typing import Literal, Self

from pydantic import Field, model_validator

from app.domain.models import Model


class Crew(Model):
    id: str
    workers: int = Field(ge=1, le=10000)
    qualifications: tuple[str, ...]
    available_from: int = Field(default=0, ge=0, le=100000)
    available_until: int = Field(default=100, ge=1, le=100000)

    @model_validator(mode="after")
    def valid_window(self) -> Self:
        if self.available_from >= self.available_until:
            raise ValueError("Crew availability window must have positive length")
        return self


class ScheduleTask(Model):
    id: str
    duration: int = Field(ge=1, le=10000)
    workers: int = Field(default=1, ge=1, le=10000)
    qualifications: tuple[str, ...] = ()
    predecessors: tuple[str, ...] = ()
    equipment: dict[str, int] = Field(default_factory=dict)
    earliest: int = Field(default=0, ge=0)
    latest_end: int = Field(default=100, ge=1)


class SchedulingProblem(Model):
    tasks: tuple[ScheduleTask, ...] = Field(min_length=1, max_length=100)
    crews: tuple[Crew, ...] = Field(min_length=1, max_length=100)
    equipment_capacities: dict[str, int] = Field(default_factory=dict)
    horizon: int = Field(default=100, ge=1, le=100000)

    @model_validator(mode="after")
    def valid_references(self) -> Self:
        ids = {t.id for t in self.tasks}
        if len(ids) != len(self.tasks) or len({c.id for c in self.crews}) != len(self.crews):
            raise ValueError("Task and crew identifiers must be unique")
        if any(not 1 <= v <= 1000000 for v in self.equipment_capacities.values()):
            raise ValueError("Equipment capacities must be between 1 and 1000000")
        for task in self.tasks:
            if not set(task.predecessors) <= ids or task.id in task.predecessors:
                raise ValueError("Unknown or self-referential predecessor")
            if any(
                k not in self.equipment_capacities or not 1 <= v <= 1000000
                for k, v in task.equipment.items()
            ):
                raise ValueError(
                    "Equipment demands must reference known capacities and be between 1 and 1000000"
                )
            if task.earliest >= task.latest_end or task.latest_end > self.horizon:
                raise ValueError("Task time window lies outside the planning horizon")
        return self


class ScheduledAssignment(Model):
    task_id: str
    crew_id: str
    start: int
    end: int


class ScheduleResult(Model):
    status: Literal["OPTIMAL", "FEASIBLE", "INFEASIBLE", "UNKNOWN"]
    assignments: tuple[ScheduledAssignment, ...] = ()
    makespan: int | None = None
    explanation: str
    solver: str = "OR-Tools CP-SAT"
    wall_time_seconds: float = 0.0
    snapshot_id: str | None = None
    proposal_only: bool = True


def validate_solution(problem: SchedulingProblem, result: ScheduleResult) -> None:
    """Independently verify every claimed feasible solution before exposing it."""
    if result.status not in {"OPTIMAL", "FEASIBLE"}:
        if result.assignments:
            raise ValueError("Non-feasible result must not contain assignments")
        return
    assignments = {a.task_id: a for a in result.assignments}
    if set(assignments) != {t.id for t in problem.tasks} or len(assignments) != len(
        result.assignments
    ):
        raise ValueError("Solution does not assign each task exactly once")
    crews = {c.id: c for c in problem.crews}
    for task in problem.tasks:
        assignment = assignments[task.id]
        crew = crews.get(assignment.crew_id)
        if (
            crew is None
            or crew.workers < task.workers
            or not set(task.qualifications) <= set(crew.qualifications)
        ):
            raise ValueError("Solution crew lacks size or qualifications")
        if assignment.end - assignment.start != task.duration:
            raise ValueError("Invalid task duration")
        if assignment.start < max(task.earliest, crew.available_from) or assignment.end > min(
            task.latest_end, crew.available_until
        ):
            raise ValueError("Assignment violates availability window")
        if any(assignments[p].end > assignment.start for p in task.predecessors):
            raise ValueError("Assignment violates precedence")
    for crew_id in crews:
        assigned = sorted(
            (a for a in result.assignments if a.crew_id == crew_id), key=lambda a: a.start
        )
        if any(left.end > right.start for left, right in zip(assigned, assigned[1:], strict=False)):
            raise ValueError("A crew is assigned to overlapping tasks")
    tasks = {t.id: t for t in problem.tasks}
    for resource, capacity in problem.equipment_capacities.items():
        changes = []
        for assignment in result.assignments:
            demand = tasks[assignment.task_id].equipment.get(resource, 0)
            changes.extend([(assignment.start, demand), (assignment.end, -demand)])
        load = 0
        for _, delta in sorted(changes):  # End events release capacity before simultaneous starts.
            load += delta
            if load > capacity:
                raise ValueError("Equipment capacity exceeded")
    if result.makespan != max(a.end for a in result.assignments):
        raise ValueError("Makespan does not match assignments")
