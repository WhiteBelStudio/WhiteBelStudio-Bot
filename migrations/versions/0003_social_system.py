"""Create social system tables.

Revision ID: 0003_social_system
Revises: 0002_user_system
"""

from alembic import op
import sqlalchemy as sa


revision = "0003_social_system"
down_revision = "0002_user_system"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "friend_requests",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("sender_id", sa.Integer(), nullable=False),
        sa.Column("recipient_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["sender_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["recipient_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("sender_id", "recipient_id", name="uq_friend_request_pair"),
    )
    op.create_index("ix_friend_requests_sender_id", "friend_requests", ["sender_id"])
    op.create_index("ix_friend_requests_recipient_id", "friend_requests", ["recipient_id"])

    op.create_table(
        "friendships",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_low_id", sa.Integer(), nullable=False),
        sa.Column("user_high_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_low_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_high_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_low_id", "user_high_id", name="uq_friendship_pair"),
    )
    op.create_index("ix_friendships_user_low_id", "friendships", ["user_low_id"])
    op.create_index("ix_friendships_user_high_id", "friendships", ["user_high_id"])


def downgrade() -> None:
    op.drop_index("ix_friendships_user_high_id", table_name="friendships")
    op.drop_index("ix_friendships_user_low_id", table_name="friendships")
    op.drop_table("friendships")
    op.drop_index("ix_friend_requests_recipient_id", table_name="friend_requests")
    op.drop_index("ix_friend_requests_sender_id", table_name="friend_requests")
    op.drop_table("friend_requests")
