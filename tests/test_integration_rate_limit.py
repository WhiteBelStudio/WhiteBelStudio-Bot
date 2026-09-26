from __future__ import annotations

import hashlib
import hmac
import json
import time
from urllib.parse import urlencode

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.app import app


def _init_data(token: str, telegram_id: int) -> str:
    values = {
        "auth_date": str(int(time.time())),
        "query_id": f"rate-limit-{telegram_id}",
        "user": json.dumps(
            {"id": telegram_id, "first_name": "Rate Limit", "is_bot": False},
            separators=(",", ":"),
        ),
    }
    check_string = "\n".join(f"{key}={value}" for key, value in sorted(values.items()))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    values["hash"] = hmac.new(
        secret,
        check_string.encode(),
        hashlib.sha256,
    ).hexdigest()
    return urlencode(values)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_authenticated_rate_limit_returns_retry_after(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("API_RATE_LIMIT_AUTHENTICATED", "1")
    monkeypatch.setenv("BOT_TOKEN", "123456:RATE-LIMIT")
    init_data = _init_data("123456:RATE-LIMIT", 990000001)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        headers = {"X-Telegram-Init-Data": init_data}
        first = await client.get("/api/v1/me", headers=headers)
        second = await client.get("/api/v1/me", headers=headers)

    assert first.status_code == 401
    assert second.status_code == 429
    assert second.headers.get("Retry-After")
    body = second.json()
    assert body["error"] == "rate_limit_exceeded"
    assert body["status_code"] == 429
