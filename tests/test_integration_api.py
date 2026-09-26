from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from urllib.parse import urlencode

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.app import app
from app.db.engine import close_db
from app.db.models import User


pytestmark = pytest.mark.integration


def _database_url() -> str:
    value = os.getenv("DATABASE_URL", "").strip()
    if not value:
        pytest.fail("DATABASE_URL is required for integration tests")
    if value.startswith("postgresql://"):
        return "postgresql+asyncpg://" + value.removeprefix("postgresql://")
    if value.startswith("postgres://"):
        return "postgresql+asyncpg://" + value.removeprefix("postgres://")
    if not value.startswith("postgresql+asyncpg://"):
        pytest.fail("Integration tests require PostgreSQL via asyncpg")
    return value


def _init_data(bot_token: str, telegram_id: int) -> str:
    values = {
        "auth_date": str(int(time.time())),
        "query_id": f"AAE-integration-{telegram_id}",
        "user": json.dumps(
            {
                "id": telegram_id,
                "first_name": "Integration",
                "is_bot": False,
            },
            separators=(",", ":"),
        ),
    }
    data_check_string = "\n".join(
        f"{key}={value}" for key, value in sorted(values.items())
    )
    secret = hmac.new(
        b"WebAppData",
        bot_token.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    values["hash"] = hmac.new(
        secret,
        data_check_string.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return urlencode(values)


@pytest.mark.asyncio
async def test_mini_app_auth_and_business_api_use_real_postgresql(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bot_token = "123456:INTEGRATION"
    telegram_id = 910000101
    monkeypatch.setenv("BOT_TOKEN", bot_token)

    engine = create_async_engine(
        _database_url(),
        pool_pre_ping=True,
        connect_args={"timeout": 10},
    )
    Session = async_sessionmaker(engine, expire_on_commit=False)

    user = User(
        telegram_id=telegram_id,
        first_name="Integration",
        username="integration_api_user",
        is_bot=False,
        is_active=True,
    )

    try:
        async with Session() as session:
            session.add(user)
            await session.commit()
            await session.refresh(user)

        init_data = _init_data(bot_token, telegram_id)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            headers = {"X-Telegram-Init-Data": init_data}

            me = await client.get("/api/v1/me", headers=headers)
            assert me.status_code == 200
            assert me.json()["id"] == user.id
            assert me.json()["telegram_id"] == telegram_id

            economy = await client.get("/api/v1/economy", headers=headers)
            assert economy.status_code == 200
            assert economy.json()["balance"] == "0.0"

            games = await client.get("/api/v1/games/profile", headers=headers)
            assert games.status_code == 200
            assert games.json()["user_id"] == user.id

            unauthenticated = await client.get("/api/v1/me")
            assert unauthenticated.status_code == 401

    finally:
        async with Session() as session:
            await session.execute(delete(User).where(User.id == user.id))
            await session.commit()
        await engine.dispose()
        await close_db()
