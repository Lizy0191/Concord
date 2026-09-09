"""Narrow local schedule-write adapter for controlled imports and simulations.

Only the application action boundary may persist the returned transition. The
reasoner receives ScheduleReader, never this writer or a repository handle.
"""

from app.domain.models import ProjectState
from app.domain.transitions import revise


class LocalScheduleWriter:
    def confirm_complete(self, state: ProjectState, work_package_id: str) -> ProjectState:
        target = state.package(work_package_id)
        if target.complete:
            return state
        packages = tuple(
            package.model_copy(update={"complete": True})
            if package.id == work_package_id
            else package
            for package in state.work_packages
        )
        return revise(state, packages, {"schedule"})
