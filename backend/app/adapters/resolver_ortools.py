import math

from app.domain.errors import CapabilityUnavailable, DomainError, ProviderError
from app.domain.scheduling import (
    ScheduledAssignment,
    ScheduleResult,
    SchedulingProblem,
    validate_solution,
)


class ORToolsResolver:
    """Real CP-SAT model: crew choice, skills, time windows, equipment, and precedence."""

    def solve(self, problem: SchedulingProblem, timeout_seconds: float = 8) -> ScheduleResult:
        if (
            isinstance(timeout_seconds, bool)
            or not isinstance(timeout_seconds, (int, float))
            or not math.isfinite(timeout_seconds)
            or timeout_seconds <= 0
        ):
            raise DomainError("Solver timeout must be a finite positive number")
        try:
            from ortools.sat.python import cp_model
        except ImportError as exc:
            raise CapabilityUnavailable("Install the optimization extra for OR-Tools") from exc
        model = cp_model.CpModel()
        starts, ends, intervals, choices = {}, {}, {}, {}
        crew_intervals = {crew.id: [] for crew in problem.crews}
        for task in problem.tasks:
            starts[task.id] = model.new_int_var(task.earliest, task.latest_end, f"start_{task.id}")
            ends[task.id] = model.new_int_var(task.earliest, task.latest_end, f"end_{task.id}")
            intervals[task.id] = model.new_interval_var(
                starts[task.id], task.duration, ends[task.id], f"task_{task.id}"
            )
            eligible = [
                c
                for c in problem.crews
                if c.workers >= task.workers and set(task.qualifications) <= set(c.qualifications)
            ]
            if not eligible:
                return ScheduleResult(
                    status="INFEASIBLE",
                    explanation=f"No crew meets size and qualifications for {task.id}.",
                )
            presence = []
            for crew in eligible:
                choice = model.new_bool_var(f"assign_{task.id}_{crew.id}")
                choices[task.id, crew.id] = choice
                presence.append(choice)
                model.add(starts[task.id] >= crew.available_from).only_enforce_if(choice)
                model.add(ends[task.id] <= crew.available_until).only_enforce_if(choice)
                crew_intervals[crew.id].append(
                    model.new_optional_interval_var(
                        starts[task.id],
                        task.duration,
                        ends[task.id],
                        choice,
                        f"crew_{task.id}_{crew.id}",
                    )
                )
            model.add_exactly_one(presence)
        for task in problem.tasks:
            for predecessor in task.predecessors:
                model.add(starts[task.id] >= ends[predecessor])
        for values in crew_intervals.values():
            if values:
                model.add_no_overlap(values)
        for resource, capacity in problem.equipment_capacities.items():
            requiring = [task for task in problem.tasks if resource in task.equipment]
            if requiring:
                model.add_cumulative(
                    [intervals[t.id] for t in requiring],
                    [t.equipment[resource] for t in requiring],
                    capacity,
                )
        makespan = model.new_int_var(0, problem.horizon, "makespan")
        model.add_max_equality(makespan, list(ends.values()))
        model.minimize(makespan)
        validation = model.validate()
        if validation:
            raise ProviderError("Scheduling input produced an invalid CP-SAT model")
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = min(max(timeout_seconds, 0.1), 30)
        solver.parameters.num_search_workers = 1  # Reproducible fixture, bounded CPU usage.
        solver.parameters.random_seed = 0
        status = solver.solve(model)
        if status == cp_model.MODEL_INVALID:
            raise ProviderError("CP-SAT rejected the model; no schedule was produced")
        if status == cp_model.INFEASIBLE:
            return ScheduleResult(
                status="INFEASIBLE",
                explanation=(
                    "The declared resource, skill, precedence, and time-window "
                    "constraints conflict."
                ),
                wall_time_seconds=solver.wall_time,
            )
        if status not in {cp_model.OPTIMAL, cp_model.FEASIBLE}:
            return ScheduleResult(
                status="UNKNOWN",
                explanation="No feasible solution was proved before the bounded solver limit.",
                wall_time_seconds=solver.wall_time,
            )
        assigned = tuple(
            ScheduledAssignment(
                task_id=t.id,
                crew_id=next(
                    c.id
                    for c in problem.crews
                    if (t.id, c.id) in choices and solver.value(choices[t.id, c.id])
                ),
                start=solver.value(starts[t.id]),
                end=solver.value(ends[t.id]),
            )
            for t in problem.tasks
        )
        result = ScheduleResult(
            status="OPTIMAL" if status == cp_model.OPTIMAL else "FEASIBLE",
            assignments=assigned,
            makespan=solver.value(makespan),
            wall_time_seconds=solver.wall_time,
            explanation=(
                "Minimized makespan with qualified non-overlapping crews, "
                "equipment capacities, predecessor order, and availability "
                "windows. This is a proposal, not a schedule write."
            ),
        )
        try:
            validate_solution(problem, result)
        except ValueError as exc:
            raise ProviderError("Solver output failed independent domain validation") from exc
        return result
