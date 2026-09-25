"""Add chat-scoped community reputation.

Revision ID: 0008_chat_reputation
Revises: 0007_community_chat
"""

from alembic import op
import sqlalchemy as sa

revision = "0008_chat_reputation"
down_revision = "0007_community_chat"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "reputation_events",
        sa.Column("chat_id", sa.Integer(), nullable=True),
    )
    op.create_index("ix_reputation_events_chat_id", "reputation_events", ["chat_id"])
    op.create_foreign_key(
        "fk_reputation_events_chat_id",
        "reputation_events",
        "community_chats",
        ["chat_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.create_table(
        "community_reputation_votes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("chat_id", sa.Integer(), nullable=False),
        sa.Column("rater_id", sa.Integer(), nullable=False),
        sa.Column("rated_id", sa.Integer(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["chat_id"], ["community_chats.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["rater_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["rated_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("chat_id", "rater_id", "rated_id", name="uq_community_rep_vote"),
    )
    op.create_index("ix_community_reputation_votes_chat_id", "community_reputation_votes", ["chat_id"])
    op.create_index("ix_community_reputation_votes_rater_id", "community_reputation_votes", ["rater_id"])
    op.create_index("ix_community_reputation_votes_rated_id", "community_reputation_votes", ["rated_id"])


def downgrade() -> None:
    op.drop_index("ix_community_reputation_votes_rated_id", table_name="community_reputation_votes")
    op.drop_index("ix_community_reputation_votes_rater_id", table_name="community_reputation_votes")
    op.drop_index("ix_community_reputation_votes_chat_id", table_name="community_reputation_votes")
    op.drop_table("community_reputation_votes")
    op.drop_constraint("fk_reputation_events_chat_id", "reputation_events", type_="foreignkey")
    op.drop_index("ix_reputation_events_chat_id", table_name="reputation_events")
    op.drop_column("reputation_events", "chat_id")
