"""Remove the retired social/friendship subsystem.

Revision ID: 0014_remove_social_system
Revises: 0013_achievements
"""

from alembic import op

revision = "0014_remove_social_system"
down_revision = "0013_achievements"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_table("friendships", if_exists=True)
    op.drop_table("friend_requests", if_exists=True)


def downgrade() -> None:
    raise RuntimeError("The retired social system is intentionally not restorable.")
