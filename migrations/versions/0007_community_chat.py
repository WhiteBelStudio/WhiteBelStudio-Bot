"""Create community chat and activity tables.

Revision ID: 0007_community_chat
Revises: 0006_community_reputation
"""

from alembic import op
import sqlalchemy as sa


revision = "0007_community_chat"
down_revision = "0006_community_reputation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "community_chats",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("telegram_chat_id", sa.BigInteger(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("chat_type", sa.String(length=32), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("rules_text", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("telegram_chat_id"),
    )
    op.create_index("ix_community_chats_telegram_chat_id", "community_chats", ["telegram_chat_id"])

    op.create_table(
        "chat_member_stats",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("chat_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("message_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("command_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["chat_id"], ["community_chats.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("chat_id", "user_id", name="uq_chat_member_stats_chat_user"),
    )
    op.create_index("ix_chat_member_stats_chat_id", "chat_member_stats", ["chat_id"])
    op.create_index("ix_chat_member_stats_user_id", "chat_member_stats", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_chat_member_stats_user_id", table_name="chat_member_stats")
    op.drop_index("ix_chat_member_stats_chat_id", table_name="chat_member_stats")
    op.drop_table("chat_member_stats")
    op.drop_index("ix_community_chats_telegram_chat_id", table_name="community_chats")
    op.drop_table("community_chats")
