from __future__ import annotations

import os
from collections.abc import AsyncIterator
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


def get_database_url() -> str:
    url = os.getenv("DATABASE_URL", "").strip()
    if not url:
        raise RuntimeError("DATABASE_URL is not set")

    if url.startswith("postgresql://"):
        url = "postgresql+asyncpg://" + url.removeprefix("postgresql://")
    elif url.startswith("postgres://"):
        url = "postgresql+asyncpg://" + url.removeprefix("postgres://")

    # PostgreSQL URLs commonly use libpq's sslmode=require.
    # asyncpg expects the equivalent parameter to be ssl=require.
    parts = urlsplit(url)
    if parts.query:
        query = parse_qsl(parts.query, keep_blank_values=True)
        normalized_query: list[tuple[str, str]] = []

        for key, value in query:
            if key == "sslmode":
                key = "ssl"
                if value in {"require", "verify-ca", "verify-full"}:
                    value = "require"
            normalized_query.append((key, value))

        url = urlunsplit(
            (
                parts.scheme,
                parts.netloc,
                parts.path,
                urlencode(normalized_query),
                parts.fragment,
            )
        )

    return url


engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def configure_engine() -> AsyncEngine:
    global engine, _session_factory

    if engine is None:
        engine = create_async_engine(
            get_database_url(),
            pool_pre_ping=True,
            pool_recycle=1800,
        )
        _session_factory = async_sessionmaker(
            engine,
            expire_on_commit=False,
        )

    return engine


async def get_session() -> AsyncIterator[AsyncSession]:
    if _session_factory is None:
        configure_engine()

    assert _session_factory is not None

    async with _session_factory() as session:
        yield session


async def init_db() -> None:
    db_engine = configure_engine()

    from app.db.models import Base

    async with db_engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    global engine, _session_factory

    if engine is not None:
        await engine.dispose()

    engine = None
    _session_factory = None
