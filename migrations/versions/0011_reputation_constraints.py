"""Harden community reputation vote values.

Revision ID: 0011_reputation_constraints
Revises: 0010_economy_shop
"""

from alembic import op
import sqlalchemy as sa

revision = "0011_reputation_constraints"
down_revision = "0010_economy_shop"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_check_constraint(
        "ck_community_reputation_votes_score",
        "community_reputation_votes",
        "score IN (-1, 1)",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_community_reputation_votes_score",
        "community_reputation_votes",
        type_="check",
    )
