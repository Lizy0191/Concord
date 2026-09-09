"""Index durable event/run identity independently of paginated presentation queries."""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("agent_runs", sa.Column("event_id", sa.String(100), nullable=True))
    connection = op.get_bind()
    runs = sa.table(
        "agent_runs",
        sa.column("id", sa.String),
        sa.column("payload", sa.JSON),
        sa.column("event_id", sa.String),
    )
    for row in connection.execute(sa.select(runs.c.id, runs.c.payload)):
        event_id = row.payload.get("event_id")
        if event_id:
            connection.execute(runs.update().where(runs.c.id == row.id).values(event_id=event_id))
    op.create_index("ix_agent_runs_event_id", "agent_runs", ["event_id"], unique=True)


def downgrade():
    op.drop_index("ix_agent_runs_event_id", table_name="agent_runs")
    with op.batch_alter_table("agent_runs") as batch:
        batch.drop_column("event_id")
