from app.domain.actions import ActionProposal, Approval, Principal
from app.domain.errors import ApprovalRequired, Conflict, PermissionDenied, StaleSnapshotError
from app.domain.models import ProjectSnapshot, ProjectState
from app.domain.runs import AgentRun

PERMISSIONS = {
    "read": {"viewer", "coordinator", "approver", "safety_approver", "admin"},
    "ingest": {"coordinator", "approver", "safety_approver", "admin"},
    "execute": {"coordinator", "approver", "safety_approver", "admin"},
    "approve": {"approver", "safety_approver", "admin"},
    "reset": {"admin"},
}


def require(principal: Principal, permission: str) -> None:
    if principal.role not in PERMISSIONS.get(permission, set()):
        raise PermissionDenied(f"Role {principal.role} lacks {permission}")


def risk_for(proposal: ActionProposal) -> int:
    return max(
        (4 if e.kind == "record_inspection" else 3 for e in proposal.resolution.effects), default=1
    )


def check_business_rules(proposal: ActionProposal) -> None:
    if proposal.risk == 5:
        raise PermissionDenied("R5 legal-liability/final safety decisions are prohibited")
    if not proposal.resolution.effects or proposal.risk < risk_for(proposal):
        raise PermissionDenied("Invalid action or understated action risk")
    if any(e.work_package_id != proposal.work_package_id for e in proposal.resolution.effects):
        raise PermissionDenied("Action scope must match its work package")


def check_fresh(snapshot: ProjectSnapshot, state: ProjectState) -> None:
    if (
        snapshot.project_id != state.project.id
        or snapshot.version != state.version
        or snapshot.sources != state.sources
    ):
        raise StaleSnapshotError(
            "Source revisions changed. Refresh and recompute before approving or executing."
        )


def check_approval(proposal: ActionProposal, approvals: list[Approval]) -> None:
    approvals = [approval for approval in approvals if approval.proposal_id == proposal.id]
    if proposal.risk >= 4:
        valid = any(
            a.level == "strong"
            and a.principal_role in {"safety_approver", "admin"}
            and a.confirmation == "APPROVE R4"
            for a in approvals
        )
    elif proposal.risk >= 3:
        valid = any(a.principal_role in {"approver", "safety_approver", "admin"} for a in approvals)
    else:
        valid = True
    if not valid:
        raise ApprovalRequired(
            "Strong human approval required" if proposal.risk >= 4 else "Human approval required"
        )


def check_proposal_generation(proposal: ActionProposal, run: AgentRun) -> None:
    if proposal.run_id != run.id or proposal.generation != run.generation:
        raise Conflict(
            "Proposal belongs to a superseded run generation; review the current proposal"
        )
