from sqlalchemy.orm import Session

from app.domain.errors import NotFound


class SessionRecords:
    """Transaction-scoped SQL session shared by the concrete record groups."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def _required(self, table, identity):
        row = self.session.get(table, identity)
        if row is None:
            raise NotFound(f"{table.__tablename__} record not found")
        return row
