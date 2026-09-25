from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.app import app


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
    with (
        patch("app.api.app.check_readiness", new=AsyncMock(return_value="0015")),
    ):
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
async def test_mini_app_valid_init_data_reaches_user_route(monkeypatch: pytest.MonkeyPatch) -> None:
    token = "123456:TEST"
    monkeypatch.setenv("BOT_TOKEN", token)
    fake_user = TelegramUser(id=123456789, is_bot=False, first_name="Test", username="test")

    async def override():
        return fake_user

    from app.api.dependencies import get_current_telegram_user
    app.dependency_overrides[get_current_telegram_user] = override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/api/v1/me",
                headers={"X-Telegram-Init-Data": _init_data(bot_token=token)},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["telegram_id"] == 123456789
