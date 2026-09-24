from __future__ import annotations

from sqlalchemy import text

from app.db.engine import configure_engine


async def check_database_connection() -> None:
    engine = configure_engine()
    async with engine.connect() as connection:
        await connection.execute(text("SELECT 1"))
