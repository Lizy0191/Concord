"""Immutable initial coordination schema, portable between SQLite and PostgreSQL."""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "projects",
        sa.Column("id", sa.String(100), primary_key=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
    )
    definitions = {
        "project_events": [("project_id", "projects.id"), ("created_at", None)],
        "snapshots": [("project_id", "projects.id")],
        "agent_runs": [("project_id", "projects.id"), ("status", None), ("created_at", None)],
        "analyses": [
            ("project_id", "projects.id"),
            ("run_id", "agent_runs.id"),
            ("created_at", None),
        ],
        "action_proposals": [("run_id", "agent_runs.id"), ("operation_id", None)],
        "approvals": [("proposal_id", "action_proposals.id")],
        "audit_records": [("project_id", "projects.id"), ("created_at", None)],
    }
    for name, fields in definitions.items():
        columns = [sa.Column("id", sa.String(100), primary_key=True)]
        for field, foreign in fields:
            args = [sa.ForeignKey(foreign)] if foreign else []
            columns.append(sa.Column(field, sa.String(100), *args, nullable=False))
        columns.append(sa.Column("payload", sa.JSON(), nullable=False))
        constraints = [sa.UniqueConstraint("operation_id")] if name == "action_proposals" else []
        op.create_table(name, *columns, *constraints)
        for field, _ in fields:
            op.create_index(f"ix_{name}_{field}", name, [field])
    op.create_table(
        "action_executions",
        sa.Column("operation_id", sa.String(100), primary_key=True),
        sa.Column(
            "proposal_id",
            sa.String(100),
            sa.ForeignKey("action_proposals.id"),
            unique=True,
            nullable=False,
        ),
        sa.Column("payload", sa.JSON(), nullable=False),
    )
    op.create_table(
        "run_events",
        sa.Column("sequence", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.String(100), sa.ForeignKey("agent_runs.id"), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
    )
    op.create_index("ix_run_events_run_id", "run_events", ["run_id"])
    op.create_table(
        "documents",
        sa.Column("id", sa.String(100), primary_key=True),
        sa.Column("project_id", sa.String(100), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("filename", sa.String(250), nullable=False),
        sa.Column("object_key", sa.String(250), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("parser", sa.String(80), nullable=False),
        sa.Column("created_at", sa.String(40), nullable=False),
    )
    op.create_index("ix_documents_project_id", "documents", ["project_id"])
    op.create_index("ix_documents_content_hash", "documents", ["content_hash"])
    op.create_table(
        "document_chunks",
        sa.Column("id", sa.String(100), primary_key=True),
        sa.Column("document_id", sa.String(100), sa.ForeignKey("documents.id"), nullable=False),
        sa.Column("project_id", sa.String(100), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
    )
    op.create_index("ix_document_chunks_document_id", "document_chunks", ["document_id"])
    op.create_index("ix_document_chunks_project_id", "document_chunks", ["project_id"])
    if op.get_bind().dialect.name == "sqlite":
        op.execute(
            "CREATE VIRTUAL TABLE document_fts USING fts5(chunk_id "
            "UNINDEXED, project_id UNINDEXED, text)"
        )


def downgrade():
    if op.get_bind().dialect.name == "sqlite":
        op.execute("DROP TABLE IF EXISTS document_fts")
    for name in [
        "document_chunks",
        "documents",
        "run_events",
        "action_executions",
        "approvals",
        "action_proposals",
        "analyses",
        "snapshots",
        "audit_records",
        "project_events",
        "agent_runs",
        "projects",
    ]:
        op.drop_table(name)
