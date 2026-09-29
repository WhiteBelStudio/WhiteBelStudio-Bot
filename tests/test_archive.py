from __future__ import annotations

from app.services.archive import archive_record, get_active_archive, list_archive, restore_record


class FakeResult:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value

    def scalars(self):
        return self

    def all(self):
        return self.value


class FakeSession:
    def __init__(self):
        self.records = []

    async def execute(self, query):
        text = str(query)
        active = [r for r in self.records if r.restored_at is None]
        if "LIMIT" in text.upper():
            return FakeResult(active)
        return FakeResult(active[0] if active else None)

    def add(self, record):
        self.records.append(record)

    async def flush(self):
        return None


def test_archive_service_validates_and_deduplicates():
    import pytest

    session = FakeSession()
    import asyncio
    first = asyncio.run(archive_record(session, entity_type="listing", entity_id=10, snapshot={"title": "A"}))
    second = asyncio.run(archive_record(session, entity_type="listing", entity_id=10, snapshot={"title": "B"}))
    assert first is second
    with pytest.raises(ValueError):
        asyncio.run(archive_record(session, entity_type="", entity_id=10, snapshot={}))


def test_archive_restore_keeps_history():
    import asyncio
    session = FakeSession()
    record = asyncio.run(archive_record(session, entity_type="listing", entity_id=11, snapshot={"title": "A"}))
    restored = asyncio.run(restore_record(session, entity_type="listing", entity_id=11, restored_by=99))
    assert restored is record
    assert record.restored_by == 99
    assert asyncio.run(get_active_archive(session, entity_type="listing", entity_id=11)) is None
