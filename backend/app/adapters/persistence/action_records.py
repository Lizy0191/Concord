from sqlalchemy import select

from app.adapters.persistence.record_session import SessionRecords
from app.adapters.persistence.tables import ApprovalRow, AuditRow, ExecutionRow, ProposalRow
from app.domain.actions import ActionExecution, ActionProposal, Approval, AuditRecord


class ActionRecords(SessionRecords):
    """Proposals, approvals, operation receipts, and append-oriented audit records."""

    def save_proposal(self, proposal: ActionProposal) -> None:
        self.session.add(
            ProposalRow(
                id=proposal.id,
                run_id=proposal.run_id,
                operation_id=proposal.operation_id,
                payload=proposal.model_dump(mode="json"),
            )
        )
        self.session.flush()

    def proposal(self, proposal_id: str) -> ActionProposal:
        return ActionProposal.model_validate(self._required(ProposalRow, proposal_id).payload)

    def proposals(self, run_id: str) -> list[ActionProposal]:
        return [
            ActionProposal.model_validate(r.payload)
            for r in self.session.scalars(select(ProposalRow).where(ProposalRow.run_id == run_id))
        ]

    def save_approval(self, approval: Approval) -> None:
        self.session.add(
            ApprovalRow(
                id=approval.id,
                proposal_id=approval.proposal_id,
                payload=approval.model_dump(mode="json"),
            )
        )

    def approvals(self, proposal_id: str) -> list[Approval]:
        return [
            Approval.model_validate(r.payload)
            for r in self.session.scalars(
                select(ApprovalRow).where(ApprovalRow.proposal_id == proposal_id)
            )
        ]

    def execution(self, operation_id: str) -> ActionExecution | None:
        row = self.session.get(ExecutionRow, operation_id)
        return ActionExecution.model_validate(row.payload) if row else None

    def save_execution(self, execution: ActionExecution) -> None:
        self.session.add(
            ExecutionRow(
                operation_id=execution.operation_id,
                proposal_id=execution.proposal_id,
                payload=execution.model_dump(mode="json"),
            )
        )

    def audit(self, record: AuditRecord) -> None:
        self.session.add(
            AuditRow(
                id=record.id,
                project_id=record.project_id,
                created_at=record.created_at.isoformat(),
                payload=record.model_dump(mode="json"),
            )
        )

    def audits(self, project_id: str) -> list[AuditRecord]:
        rows = self.session.scalars(
            select(AuditRow)
            .where(AuditRow.project_id == project_id)
            .order_by(AuditRow.created_at.desc())
            .limit(200)
        )
        return [AuditRecord.model_validate(r.payload) for r in rows]
