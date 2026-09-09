import hashlib
from collections.abc import Iterator
from contextlib import contextmanager, nullcontext
from pathlib import Path
from typing import Any

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, event, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.adapters.persistence.tables import ProjectRow


def make_engine(url: str) -> Engine:
    # The server extra provides psycopg v3, not SQLAlchemy's legacy default
    # psycopg2 driver. Preserve explicitly selected drivers.
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url.removeprefix("postgresql://")
    kwargs: dict[str, Any] = {"pool_pre_ping": True, "hide_parameters": True}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False, "timeout": 15}
        if ":memory:" in url:
            kwargs["poolclass"] = StaticPool
    if url.startswith("postgresql"):
        kwargs["connect_args"] = {"connect_timeout": 5}
        kwargs["pool_timeout"] = 5
    engine = create_engine(url, **kwargs)
    if engine.dialect.name == "sqlite":

        @event.listens_for(engine, "connect")
        def set_pragmas(connection, _record):
            cursor = connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA busy_timeout=15000")
            cursor.close()

    return engine


def migrate(engine: Engine) -> None:
    config = Config()
    source = Path(__file__).resolve().parents[3] / "migrations"
    bundled = Path(__file__).resolve().parents[2] / "migrations"
    config.set_main_option("script_location", str(source if source.is_dir() else bundled))
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")


class SQLRepositoryFactory:
    def __init__(self, engine: Engine, telemetry=None) -> None:
        self.engine, self.telemetry = engine, telemetry

    @contextmanager
    def open(self, project_id: str | None = None, *, write: bool = False) -> Iterator:
        from app.adapters.persistence.repository import SQLCoordinationRepository

        trace = (
            self.telemetry.span(
                "database.transaction", database=self.engine.dialect.name, write=write
            )
            if self.telemetry
            else nullcontext()
        )
        with trace, Session(self.engine, expire_on_commit=False) as session:
            try:
                if write and self.engine.dialect.name == "sqlite":
                    session.connection().exec_driver_sql("BEGIN IMMEDIATE")
                elif write and project_id:
                    if self.engine.dialect.name == "postgresql":
                        # Row locks cannot serialize the first insert of a project.
                        # This transaction-scoped, stable key also covers that gap.
                        key = int.from_bytes(
                            hashlib.sha256(("cca:project:" + project_id).encode()).digest()[:8],
                            "big",
                            signed=True,
                        )
                        session.execute(text("SET LOCAL lock_timeout = '15000ms'"))
                        session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": key})
                    session.execute(
                        select(ProjectRow).where(ProjectRow.id == project_id).with_for_update()
                    )
                yield SQLCoordinationRepository(session)
                if write:
                    session.commit()
            except BaseException:
                session.rollback()
                raise
