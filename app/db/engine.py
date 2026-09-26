from __future__ import annotations

import os
from collections.abc import AsyncIterator
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy.pool import NullPool
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
            elif key == "channel_binding":
                # asyncpg does not accept libpq's channel_binding URL parameter.
                continue

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
        app_env = os.getenv("APP_ENV", "production").lower()
        database_url = get_database_url()
        if app_env == "production" and not database_url.startswith("postgresql+asyncpg://"):
            raise RuntimeError("Production DATABASE_URL must use PostgreSQL")

        engine_kwargs: dict[str, object] = {
            "pool_pre_ping": True,
            "pool_recycle": int(os.getenv("DB_POOL_RECYCLE", "1800")),
            "pool_timeout": int(os.getenv("DB_POOL_TIMEOUT", "30")),
        }
        if database_url.startswith("postgresql+asyncpg://"):
            if app_env == "test":
                engine_kwargs["poolclass"] = NullPool
            engine_kwargs["pool_size"] = int(os.getenv("DB_POOL_SIZE", "5"))
            engine_kwargs["max_overflow"] = int(os.getenv("DB_MAX_OVERFLOW", "10"))
            engine_kwargs["connect_args"] = {
                "timeout": float(os.getenv("DB_CONNECT_TIMEOUT", "10"))
            }

        engine = create_async_engine(database_url, **engine_kwargs)
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
    """Initialize a development/test schema without bypassing production migrations."""
    if os.getenv("APP_ENV", "production").lower() == "production":
        raise RuntimeError("init_db() is disabled in production; use Alembic migrations")

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
