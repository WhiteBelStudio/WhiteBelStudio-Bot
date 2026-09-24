"""Create community reputation events.

Revision ID: 0006_community_reputation
Revises: 0005_reputation
"""

from alembic import op
import sqlalchemy as sa


revision = "0006_community_reputation"
down_revision = "0005_reputation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "reputation_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("actor_id", sa.Integer(), nullable=True),
        sa.Column("delta", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_reputation_events_user_id", "reputation_events", ["user_id"])
    op.create_index("ix_reputation_events_actor_id", "reputation_events", ["actor_id"])


def downgrade() -> None:
    op.drop_index("ix_reputation_events_actor_id", table_name="reputation_events")
    op.drop_index("ix_reputation_events_user_id", table_name="reputation_events")
    op.drop_table("reputation_events")
