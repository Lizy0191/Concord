from app.domain.scheduling import Crew, ScheduleTask, SchedulingProblem


def coordination_fixture() -> SchedulingProblem:
    return SchedulingProblem(
        horizon=16,
        crews=(
            Crew(id="crew-mep", workers=4, qualifications=("duct", "inspect"), available_until=16),
            Crew(id="crew-electrical", workers=3, qualifications=("electric",), available_until=16),
        ),
        equipment_capacities={"scissor-lift": 1, "inspection-kit": 1},
        tasks=(
            ScheduleTask(
                id="duct-l02",
                duration=4,
                workers=4,
                qualifications=("duct",),
                equipment={"scissor-lift": 1},
                latest_end=12,
            ),
            ScheduleTask(
                id="electrical-l02",
                duration=3,
                workers=3,
                qualifications=("electric",),
                equipment={"scissor-lift": 1},
                latest_end=13,
            ),
            ScheduleTask(
                id="inspection-l02",
                duration=2,
                qualifications=("inspect",),
                predecessors=("duct-l02", "electrical-l02"),
                equipment={"inspection-kit": 1},
                latest_end=16,
            ),
        ),
    )
