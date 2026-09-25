"""Add core game system profile.

Revision ID: 0009_game_system
Revises: 0008_chat_reputation
"""

from alembic import op
import sqlalchemy as sa

revision = "0009_game_system"
down_revision = "0008_chat_reputation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "game_profiles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("level", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("experience", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("games_played", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("wins", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("losses", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("draws", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", name="uq_game_profile_user"),
    )
    op.create_index("ix_game_profiles_user_id", "game_profiles", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_game_profiles_user_id", table_name="game_profiles")
    op.drop_table("game_profiles")
