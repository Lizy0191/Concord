"""Commit a generation-bound SDK identity before any external dispatch.

A resumed domain run must not join an execution that is still cancelling or
replay decisions/checkpoints belonging to its previous generation. Its business
run ID and operation receipts remain unchanged. Legacy generation-zero rows keep
their existing execution IDs.
"""

from uuid import NAMESPACE_URL, uuid5

from app.domain.runs import AgentRun
from app.ports.coordination import RepositoryFactory


def bind_execution(factory: RepositoryFactory, run_id: str, runtime: str) -> AgentRun:
    with factory.open() as repo:
        run = repo.run(run_id)
    if run.runtime_generation == run.generation:
        return run
    with factory.open(run.project_id, write=True) as repo:
        run = repo.run(run_id)
        if run.runtime_generation != run.generation:
            identity = str(
                uuid5(NAMESPACE_URL, f"cca:{runtime}:generation:{run.id}:{run.generation}")
            )
            run = run.model_copy(
                update={"runtime_execution_id": identity, "runtime_generation": run.generation}
            )
            repo.save_run(run)
        return run
