"""Optional PostgreSQL-only derived retrieval storage."""

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import VECTOR

revision = "v0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "document_embeddings",
        sa.Column(
            "chunk_id", sa.String(100), sa.ForeignKey("document_chunks.id"), primary_key=True
        ),
        sa.Column("model", sa.String(250), primary_key=True),
        sa.Column("model_version", sa.String(250), primary_key=True),
        sa.Column("project_id", sa.String(100), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("document_id", sa.String(100), sa.ForeignKey("documents.id"), nullable=False),
        sa.Column("source_hash", sa.String(64), nullable=False),
        sa.Column("dimensions", sa.Integer, nullable=False),
        sa.Column("embedding", VECTOR(), nullable=False),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.CheckConstraint("dimensions = vector_dims(embedding)", name="ck_embedding_dimensions"),
    )
    op.create_index(
        "ix_embeddings_project_model",
        "document_embeddings",
        ["project_id", "model", "model_version", "dimensions"],
    )


def downgrade():
    op.drop_index("ix_embeddings_project_model", table_name="document_embeddings")
    op.drop_table("document_embeddings")
    # Do not drop a shared database extension used by other applications.
