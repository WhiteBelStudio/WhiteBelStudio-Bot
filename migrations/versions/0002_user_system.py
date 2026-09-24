"""Add user profile and settings.

Revision ID: 0002_user_system
Revises: 0001_initial_users
"""

from alembic import op
import sqlalchemy as sa


revision = "0002_user_system"
down_revision = "0001_initial_users"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("language_code", sa.String(length=16), nullable=True))
    op.add_column("users", sa.Column("is_bot", sa.Boolean(), server_default=sa.false(), nullable=False))
    op.add_column("users", sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False))
    op.add_column("users", sa.Column("bio", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("city", sa.String(length=128), nullable=True))
    op.add_column("users", sa.Column("avatar_file_id", sa.String(length=256), nullable=True))
    op.add_column(
        "users",
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_table(
        "user_settings",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column(
            "notifications_enabled",
            sa.Boolean(),
            server_default=sa.true(),
            nullable=False,
        ),
        sa.Column(
            "show_profile",
            sa.Boolean(),
            server_default=sa.true(),
            nullable=False,
        ),
        sa.Column(
            "language",
            sa.String(length=16),
            server_default="ru",
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
    )


def downgrade() -> None:
    op.drop_table("user_settings")
    op.drop_column("users", "last_seen_at")
    op.drop_column("users", "avatar_file_id")
    op.drop_column("users", "city")
    op.drop_column("users", "bio")
    op.drop_column("users", "is_active")
    op.drop_column("users", "is_bot")
    op.drop_column("users", "language_code")
