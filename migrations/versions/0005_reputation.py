"""Create reputation ratings.

Revision ID: 0005_reputation
Revises: 0004_communication
"""

from alembic import op
import sqlalchemy as sa


revision = "0005_reputation"
down_revision = "0004_communication"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "reputation_ratings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("rater_id", sa.Integer(), nullable=False),
        sa.Column("rated_id", sa.Integer(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("comment", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["rater_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["rated_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("rater_id", "rated_id", name="uq_reputation_rating_pair"),
        sa.CheckConstraint("score >= 1 AND score <= 5", name="ck_reputation_score_range"),
    )
    op.create_index("ix_reputation_ratings_rater_id", "reputation_ratings", ["rater_id"])
    op.create_index("ix_reputation_ratings_rated_id", "reputation_ratings", ["rated_id"])


def downgrade() -> None:
    op.drop_index("ix_reputation_ratings_rated_id", table_name="reputation_ratings")
    op.drop_index("ix_reputation_ratings_rater_id", table_name="reputation_ratings")
    op.drop_table("reputation_ratings")
