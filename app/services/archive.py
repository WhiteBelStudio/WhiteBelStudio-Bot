"""Archive service with snapshot, restore and history support."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ArchiveRecord


async def archive_record(
    session: AsyncSession,
    *,
    entity_type: str,
    entity_id: int,
    snapshot: dict,
    archived_by: int | None = None,
    reason: str | None = None,
) -> ArchiveRecord:
    """Create an immutable archive snapshot and return it."""
    entity_type = entity_type.strip()
    if not entity_type:
        raise ValueError("entity_type must not be empty")
    if entity_id <= 0:
        raise ValueError("entity_id must be positive")
    if not isinstance(snapshot, dict):
        raise TypeError("snapshot must be a dict")

    active = await session.execute(
        select(ArchiveRecord).where(
            ArchiveRecord.entity_type == entity_type,
            ArchiveRecord.entity_id == entity_id,
            ArchiveRecord.restored_at.is_(None),
        )
    )
    existing = active.scalar_one_or_none()
    if existing is not None:
        return existing

    record = ArchiveRecord(
        entity_type=entity_type,
        entity_id=entity_id,
        snapshot=dict(snapshot),
        archived_by=archived_by,
        reason=reason.strip() if reason else None,
    )
    session.add(record)
    await session.flush()
    return record


async def restore_record(
    session: AsyncSession,
    *,
    entity_type: str,
    entity_id: int,
    restored_by: int | None = None,
) -> ArchiveRecord | None:
    """Mark the active archive entry restored without deleting its history."""
    result = await session.execute(
        select(ArchiveRecord).where(
            ArchiveRecord.entity_type == entity_type,
            ArchiveRecord.entity_id == entity_id,
            ArchiveRecord.restored_at.is_(None),
        )
    )
    record = result.scalar_one_or_none()
    if record is None:
        return None
    record.restored_by = restored_by
    record.restored_at = datetime.now(timezone.utc)
    await session.flush()
    return record


async def get_active_archive(
    session: AsyncSession, *, entity_type: str, entity_id: int
) -> ArchiveRecord | None:
    result = await session.execute(
        select(ArchiveRecord).where(
            ArchiveRecord.entity_type == entity_type,
            ArchiveRecord.entity_id == entity_id,
            ArchiveRecord.restored_at.is_(None),
        )
    )
    return result.scalar_one_or_none()


async def list_archive(
    session: AsyncSession, *, entity_type: str | None = None, limit: int = 100
) -> list[ArchiveRecord]:
    limit = max(1, min(limit, 500))
    query = select(ArchiveRecord).where(ArchiveRecord.restored_at.is_(None))
    if entity_type:
        query = query.where(ArchiveRecord.entity_type == entity_type.strip())
    result = await session.execute(query.order_by(ArchiveRecord.archived_at.desc()).limit(limit))
    return list(result.scalars().all())
