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
    body = response.json()
    assert body["error"] == "internal_error"
    assert body["detail"] == "Internal server error"
    assert body["status_code"] == 500
    assert body["request_id"] == response.headers["X-Request-ID"]


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


@pytest.mark.asyncio
async def test_request_id_is_returned_and_is_uuid() -> None:
    from uuid import UUID

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/health/live")

    request_id = response.headers["X-Request-ID"]
    assert UUID(request_id).version == 4


@pytest.mark.asyncio
async def test_request_id_is_preserved_when_valid_uuid_is_supplied() -> None:
    request_id = "12345678-1234-4234-8234-123456789abc"

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(
            "/health/live",
            headers={"X-Request-ID": request_id},
        )

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == request_id


@pytest.mark.asyncio
async def test_invalid_request_id_is_replaced() -> None:
    from uuid import UUID

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(
            "/health/live",
            headers={"X-Request-ID": "not-a-uuid"},
        )

    generated = response.headers["X-Request-ID"]
    assert UUID(generated).version == 4


@pytest.mark.asyncio
async def test_structured_access_log_contains_request_context(caplog: pytest.LogCaptureFixture) -> None:
    import json
    import logging

    caplog.set_level(logging.INFO, logger="app.api.access")
    request_id = "12345678-1234-4234-8234-123456789abc"

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(
            "/health/live",
            headers={"X-Request-ID": request_id},
        )

    assert response.status_code == 200
    records = [
        record for record in caplog.records
        if record.name == "app.api.access" and record.message == "http_request"
    ]
    assert records
    record = records[-1]
    assert record.request_id == request_id
    assert record.method == "GET"
    assert record.path == "/health/live"
    assert record.status_code == 200
    assert isinstance(record.duration_ms, float)


@pytest.mark.asyncio
async def test_http_errors_use_unified_shape() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/api/v1/not-found")

    assert response.status_code == 404
    body = response.json()
    assert body["error"] == "http_error"
    assert body["detail"] == "Not Found"
    assert body["status_code"] == 404
    assert body["request_id"] == response.headers["X-Request-ID"]


@pytest.mark.asyncio
async def test_validation_errors_use_unified_shape() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/api/v1/conversations/not-an-integer/messages")

    assert response.status_code == 422
    body = response.json()
    assert body["error"] == "validation_error"
    assert body["detail"] == "Request validation failed"
    assert body["status_code"] == 422
    assert body["request_id"] == response.headers["X-Request-ID"]
    assert body["errors"]
