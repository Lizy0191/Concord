from sqlalchemy import select

from app.adapters.persistence.record_session import SessionRecords
from app.adapters.persistence.tables import CapabilityJobRow, RunRow, StreamRow
from app.domain.errors import NotFound
from app.domain.jobs import CapabilityJob
from app.domain.runs import AgentRun, StreamEvent


class RunRecords(SessionRecords):
    """Durable run/job records and bounded SSE history; never opens or commits a session."""

    def save_run(self, run: AgentRun) -> None:
        self.session.merge(
            RunRow(
                id=run.id,
                project_id=run.project_id,
                event_id=run.event_id,
                status=run.status,
                created_at=run.created_at.isoformat(),
                payload=run.model_dump(mode="json"),
            )
        )
        self.session.flush()

    def run(self, run_id: str) -> AgentRun:
        return AgentRun.model_validate(self._required(RunRow, run_id).payload)

    def runs(self, project_id: str | None = None) -> list[AgentRun]:
        query = select(RunRow)
        if project_id:
            query = query.where(RunRow.project_id == project_id)
        return [
            AgentRun.model_validate(r.payload)
            for r in self.session.scalars(query.order_by(RunRow.created_at.desc()).limit(200))
        ]

    def run_for_event(self, event_id: str) -> AgentRun:
        row = self.session.scalar(select(RunRow).where(RunRow.event_id == event_id))
        if row is None:
            raise NotFound("Event has no durable run record")
        return AgentRun.model_validate(row.payload)

    def pending_runs(self, project_id: str | None = None) -> list[AgentRun]:
        query = select(RunRow).where(RunRow.status.in_(["QUEUED", "RUNNING", "WAITING_APPROVAL"]))
        if project_id:
            query = query.where(RunRow.project_id == project_id)
        return [AgentRun.model_validate(row.payload) for row in self.session.scalars(query)]

    def emit(self, run_id: str, payload: dict) -> None:
        self.session.add(StreamRow(run_id=run_id, payload=payload))

    def stream_tail(self, run_id: str, limit: int = 200) -> list[StreamEvent]:
        if not 1 <= limit <= 200:
            raise ValueError("Timeline window must contain 1 to 200 events")
        rows = list(
            self.session.scalars(
                select(StreamRow)
                .where(StreamRow.run_id == run_id)
                .order_by(StreamRow.sequence.desc())
                .limit(limit)
            )
        )
        return [
            StreamEvent(sequence=r.sequence, run_id=r.run_id, payload=r.payload)
            for r in reversed(rows)
        ]

    def stream(self, run_id: str, after: int = 0) -> list[StreamEvent]:
        rows = self.session.scalars(
            select(StreamRow)
            .where(StreamRow.run_id == run_id, StreamRow.sequence > after)
            .order_by(StreamRow.sequence)
            .limit(200)
        )
        return [StreamEvent(sequence=r.sequence, run_id=r.run_id, payload=r.payload) for r in rows]

    def save_job(self, job: CapabilityJob) -> None:
        self.session.merge(
            CapabilityJobRow(
                id=job.id, project_id=job.project_id, payload=job.model_dump(mode="json")
            )
        )
        self.session.flush()

    def job(self, job_id: str) -> CapabilityJob:
        return CapabilityJob.model_validate(self._required(CapabilityJobRow, job_id).payload)
