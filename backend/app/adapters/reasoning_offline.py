from app.domain.models import Evidence, ProjectSnapshot, ProjectState
from app.domain.runs import ReasoningProposal


class OfflineReasoningEngine:
    mode = "offline"

    def interpret(
        self, state: ProjectState, snapshot: ProjectSnapshot, evidence: tuple[Evidence, ...]
    ) -> ReasoningProposal:
        packages = {item.work_package_id for item in evidence}
        return ReasoningProposal(
            summary=(
                f"Checked {len(state.work_packages)} work packages "
                f"against snapshot version {snapshot.version}. "
                f"Found {len(evidence)} recorded constraint facts "
                f"affecting {len(packages)} work packages."
            ),
            evidence_ids=tuple(item.id for item in evidence),
            limitations=("Offline deterministic analysis; external confirmations are simulated.",),
            mode=self.mode,
        )
