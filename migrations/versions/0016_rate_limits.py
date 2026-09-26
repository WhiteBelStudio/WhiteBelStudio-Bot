"""Add PostgreSQL-backed API rate-limit buckets.

Revision ID: 0016_rate_limits
Revises: 0015_database_integrity
"""

from alembic import op
import sqlalchemy as sa

revision = "0016_rate_limits"
down_revision = "0015_database_integrity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "rate_limit_buckets",
        sa.Column("bucket_key", sa.String(length=255), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("request_count", sa.Integer(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("bucket_key"),
        sa.CheckConstraint("request_count >= 0", name="ck_rate_limit_request_count"),
    )
    op.create_index(
        "ix_rate_limit_buckets_window_start",
        "rate_limit_buckets",
        ["window_start"],
    )


def downgrade() -> None:
    op.drop_index("ix_rate_limit_buckets_window_start", table_name="rate_limit_buckets")
    op.drop_table("rate_limit_buckets")
