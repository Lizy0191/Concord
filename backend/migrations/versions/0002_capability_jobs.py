"""Capability inputs/results, IFC indexes, and durable source evidence."""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "capability_jobs",
        sa.Column("id", sa.String(100), primary_key=True),
        sa.Column("project_id", sa.String(100), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
    )
    op.create_index("ix_capability_jobs_project_id", "capability_jobs", ["project_id"])
    op.create_table(
        "bim_indexes",
        sa.Column("project_id", sa.String(100), primary_key=True),
        sa.Column("payload", sa.JSON(), nullable=False),
    )
    op.create_table(
        "source_evidence",
        sa.Column("id", sa.String(100), primary_key=True),
        sa.Column("source_id", sa.String(240), nullable=False),
        sa.Column("snapshot_id", sa.String(100), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
    )
    op.create_index("ix_source_evidence_source_id", "source_evidence", ["source_id"])
    op.create_index("ix_source_evidence_snapshot_id", "source_evidence", ["snapshot_id"])


def downgrade():
    op.drop_table("source_evidence")
    op.drop_table("bim_indexes")
    op.drop_table("capability_jobs")
