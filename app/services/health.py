from __future__ import annotations

from app.db.health import check_database_connection, check_database_schema


async def check_readiness() -> str:
    """Run application readiness checks behind the service boundary."""
    await check_database_connection()
    return await check_database_schema()
