import pytest
from app.adapters.scheduling_fixture import coordination_fixture
from app.domain.scheduling import ScheduledAssignment, ScheduleResult, validate_solution


def valid_result():
    return ScheduleResult(
        status="FEASIBLE",
        makespan=9,
        explanation="Independently validated contract fixture",
        assignments=(
            ScheduledAssignment(task_id="duct-l02", crew_id="crew-mep", start=0, end=4),
            ScheduledAssignment(
                task_id="electrical-l02", crew_id="crew-electrical", start=4, end=7
            ),
            ScheduledAssignment(task_id="inspection-l02", crew_id="crew-mep", start=7, end=9),
        ),
    )


def test_independent_scheduling_contract_and_capacity_violation():
    problem = coordination_fixture()
    result = valid_result()
    validate_solution(problem, result)
    overlap = result.model_copy(
        update={
            "assignments": (
                result.assignments[0],
                result.assignments[1].model_copy(update={"start": 0, "end": 3}),
                result.assignments[2],
            )
        }
    )
    with pytest.raises(ValueError, match="Equipment"):
        validate_solution(problem, overlap)


def test_independent_scheduling_contract_rejects_bad_crew_and_precedence():
    result = valid_result()
    unqualified = result.model_copy(
        update={
            "assignments": (
                result.assignments[0].model_copy(update={"crew_id": "crew-electrical"}),
                *result.assignments[1:],
            )
        }
    )
    with pytest.raises(ValueError, match="qualifications"):
        validate_solution(coordination_fixture(), unqualified)
    early = result.model_copy(
        update={
            "assignments": (
                *result.assignments[:2],
                result.assignments[2].model_copy(update={"start": 3, "end": 5}),
            )
        }
    )
    with pytest.raises(ValueError, match="precedence"):
        validate_solution(coordination_fixture(), early)


def test_solver_infeasible_never_contains_a_fake_solution():
    result = ScheduleResult(status="INFEASIBLE", explanation="Unavailable qualified crew")
    validate_solution(coordination_fixture(), result)
    with pytest.raises(ValueError):
        validate_solution(
            coordination_fixture(),
            result.model_copy(update={"assignments": valid_result().assignments}),
        )


@pytest.mark.parametrize("timeout", [float("nan"), float("inf"), -1, 0, True, "8"])
def test_ortools_rejects_invalid_time_budget_before_sdk_import(timeout):
    from app.adapters.resolver_ortools import ORToolsResolver
    from app.domain.errors import DomainError

    with pytest.raises(DomainError, match="finite positive"):
        ORToolsResolver().solve(coordination_fixture(), timeout_seconds=timeout)


@pytest.mark.parametrize("target", ["crew-start", "crew-end", "capacity", "demand"])
def test_scheduler_rejects_unbounded_native_integer_inputs(target):
    from app.domain.scheduling import SchedulingProblem
    from pydantic import ValidationError

    data = coordination_fixture().model_dump()
    if target == "crew-start":
        data["crews"][0]["available_from"] = 2**80
    elif target == "crew-end":
        data["crews"][0]["available_until"] = 2**80
    elif target == "capacity":
        resource = next(iter(data["equipment_capacities"]))
        data["equipment_capacities"][resource] = 2**80
    else:
        resource = next(iter(data["equipment_capacities"]))
        data["tasks"][0]["equipment"][resource] = 2**80
    with pytest.raises(ValidationError):
        SchedulingProblem.model_validate(data)
