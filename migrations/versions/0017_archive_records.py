"""Add durable archive records.

Revision ID: 0017_archive_records
Revises: 0016_rate_limits
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0017_archive_records"
down_revision = "0016_rate_limits"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "archive_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("entity_id", sa.BigInteger(), nullable=False),
        sa.Column("snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("reason", sa.String(length=255), nullable=True),
        sa.Column("archived_by", sa.BigInteger(), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("restored_by", sa.BigInteger(), nullable=True),
        sa.Column("restored_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_archive_records_entity", "archive_records", ["entity_type", "entity_id"])
    op.create_index("ix_archive_records_archived_at", "archive_records", ["archived_at"])
    op.create_index(
        "uq_archive_records_active_entity",
        "archive_records",
        ["entity_type", "entity_id"],
        unique=True,
        postgresql_where=sa.text("restored_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_archive_records_active_entity", table_name="archive_records")
    op.drop_index("ix_archive_records_archived_at", table_name="archive_records")
    op.drop_index("ix_archive_records_entity", table_name="archive_records")
    op.drop_table("archive_records")
