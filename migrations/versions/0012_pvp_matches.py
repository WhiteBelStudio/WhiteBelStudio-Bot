"""Add skill-based PvP mini-game matches.

Revision ID: 0012_pvp_matches
Revises: 0011_reputation_constraints
"""

from alembic import op
import sqlalchemy as sa

revision = "0012_pvp_matches"
down_revision = "0011_reputation_constraints"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pvp_matches",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("creator_id", sa.Integer(), nullable=False),
        sa.Column("opponent_id", sa.Integer(), nullable=True),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("answer", sa.String(256), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("creator_answer", sa.Boolean(), nullable=True),
        sa.Column("opponent_answer", sa.Boolean(), nullable=True),
        sa.Column("winner_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["creator_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["opponent_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["winner_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_pvp_matches_creator_id", "pvp_matches", ["creator_id"])
    op.create_index("ix_pvp_matches_opponent_id", "pvp_matches", ["opponent_id"])
    op.create_index("ix_pvp_matches_status", "pvp_matches", ["status"])


def downgrade() -> None:
    op.drop_index("ix_pvp_matches_status", table_name="pvp_matches")
    op.drop_index("ix_pvp_matches_opponent_id", table_name="pvp_matches")
    op.drop_index("ix_pvp_matches_creator_id", table_name="pvp_matches")
    op.drop_table("pvp_matches")
