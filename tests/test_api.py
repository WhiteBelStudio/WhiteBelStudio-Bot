from __future__ import annotations

import hashlib
import hmac
import json
import time
from unittest.mock import AsyncMock, patch
from urllib.parse import urlencode

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.app import app
from app.db.models import User


def _init_data(
    *,
    bot_token: str,
    telegram_id: int = 123456789,
    auth_date: int | None = None,
) -> str:
    values = {
        "auth_date": str(auth_date if auth_date is not None else int(time.time())),
        "query_id": "AAE-test",
        "user": json.dumps(
            {
                "id": telegram_id,
                "first_name": "Test",
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
async def test_liveness_is_independent_of_database() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_api_health_reports_version() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/api/v1/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["version"] == app.version


@pytest.mark.asyncio
async def test_readiness_requires_database() -> None:
    with patch(
        "app.api.app.check_readiness",
        new=AsyncMock(side_effect=RuntimeError("database unavailable")),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/health/ready")

    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error"}


@pytest.mark.asyncio
async def test_readiness_returns_migration_revision() -> None:
    with patch("app.api.app.check_readiness", new=AsyncMock(return_value="0015")):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "database": "ok",
        "revision": "0015",
    }


@pytest.mark.asyncio
async def test_mini_app_missing_auth_is_rejected() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/api/v1/me")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_mini_app_invalid_init_data_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BOT_TOKEN", "123456:TEST")
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(
            "/api/v1/me",
            headers={"X-Telegram-Init-Data": "invalid"},
        )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_mini_app_resolves_existing_chat_user(monkeypatch: pytest.MonkeyPatch) -> None:
    token = "123456:TEST"
    monkeypatch.setenv("BOT_TOKEN", token)
    now = int(time.time())
    user = User(
        id=7,
        telegram_id=123456789,
        first_name="Test",
        username="test",
        is_bot=False,
        is_active=True,
    )

    async def override() -> User:
        return user

    from app.api.dependencies import get_current_telegram_user

    app.dependency_overrides[get_current_telegram_user] = override
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(
                "/api/v1/me",
                headers={
                    "X-Telegram-Init-Data": _init_data(
                        bot_token=token,
                        auth_date=now,
                    )
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == 7
    assert body["telegram_id"] == 123456789
    assert body["username"] == "test"


@pytest.mark.asyncio
async def test_business_api_requires_mini_app_auth() -> None:
    protected_paths = (
        "/api/v1/me",
        "/api/v1/economy",
        "/api/v1/economy/transactions",
        "/api/v1/games/profile",
        "/api/v1/reputation",
        "/api/v1/achievements",
        "/api/v1/achievements/progress",
        "/api/v1/shop/items",
        "/api/v1/shop/inventory",
        "/api/v1/conversations/1/messages",
    )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        for path in protected_paths:
            response = await client.get(path)
            assert response.status_code == 401, path
