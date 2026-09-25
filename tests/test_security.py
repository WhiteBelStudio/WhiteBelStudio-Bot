from __future__ import annotations

import hashlib
import hmac
import json
import time
from urllib.parse import urlencode

import pytest

from app.services.security import TelegramInitDataError, validate_telegram_init_data


def make_init_data(bot_token: str, *, auth_date: int | None = None, telegram_id: int = 123) -> str:
    values = {
        "auth_date": str(auth_date if auth_date is not None else int(time.time())),
        "query_id": "AAE-test",
        "user": json.dumps({"id": telegram_id, "first_name": "Test", "is_bot": False}, separators=(",", ":")),
    }
    data_check_string = "\n".join(f"{key}={value}" for key, value in sorted(values.items()))
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    values["hash"] = hmac.new(secret, data_check_string.encode(), hashlib.sha256).hexdigest()
    return urlencode(values)


def test_valid_init_data(monkeypatch: pytest.MonkeyPatch) -> None:
    token = "123456:TEST"
    monkeypatch.setenv("BOT_TOKEN", token)
    result = validate_telegram_init_data(make_init_data(token))
    assert result.user.id == 123
    assert result.query_id == "AAE-test"


def test_duplicate_keys_are_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    token = "123456:TEST"
    monkeypatch.setenv("BOT_TOKEN", token)
    data = make_init_data(token)
    with pytest.raises(TelegramInitDataError):
        validate_telegram_init_data(data + "&auth_date=1")


def test_invalid_hash_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BOT_TOKEN", "123456:TEST")
    with pytest.raises(TelegramInitDataError):
        validate_telegram_init_data("auth_date=1&user=%7B%22id%22%3A123%7D&hash=bad")


def test_expired_init_data_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    token = "123456:TEST"
    monkeypatch.setenv("BOT_TOKEN", token)
    with pytest.raises(TelegramInitDataError, match="Expired"):
        validate_telegram_init_data(make_init_data(token, auth_date=100), now=100 + 86401)


def test_future_init_data_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    token = "123456:TEST"
    monkeypatch.setenv("BOT_TOKEN", token)
    with pytest.raises(TelegramInitDataError, match="Expired"):
        validate_telegram_init_data(make_init_data(token, auth_date=1000), now=1000 - 61)


@pytest.mark.asyncio
async def test_authentication_binds_to_existing_chat_user(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services import security

    token = "123456:TEST"
    monkeypatch.setenv("BOT_TOKEN", token)
    chat_user = object()

    async def fake_get_user_by_telegram_id(session: object, telegram_id: int) -> object:
        assert telegram_id == 123
        return chat_user

    class DummySession:
        pass

    async def fake_get_session():
        yield DummySession()

    monkeypatch.setattr(security, "get_user_by_telegram_id", fake_get_user_by_telegram_id)
    monkeypatch.setattr(security, "get_session", fake_get_session)

    result = await security.authenticate_telegram_init_data(make_init_data(token))
    assert result is chat_user


@pytest.mark.asyncio
async def test_authentication_rejects_unregistered_chat_user(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services import security

    token = "123456:TEST"
    monkeypatch.setenv("BOT_TOKEN", token)

    async def fake_get_user_by_telegram_id(session: object, telegram_id: int) -> None:
        return None

    async def fake_get_session():
        yield object()

    monkeypatch.setattr(security, "get_user_by_telegram_id", fake_get_user_by_telegram_id)
    monkeypatch.setattr(security, "get_session", fake_get_session)

    with pytest.raises(TelegramInitDataError, match="not registered"):
        await security.authenticate_telegram_init_data(make_init_data(token))


@pytest.mark.asyncio
async def test_authentication_rejects_inactive_chat_user(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services import security
    from app.db.models import User

    token = "123456:TEST"
    monkeypatch.setenv("BOT_TOKEN", token)
    chat_user = User(
        id=7,
        telegram_id=123,
        first_name="Test",
        is_bot=False,
        is_active=False,
    )

    async def fake_get_user_by_telegram_id(session: object, telegram_id: int) -> User:
        return chat_user

    async def fake_get_session():
        yield object()

    monkeypatch.setattr(security, "get_user_by_telegram_id", fake_get_user_by_telegram_id)
    monkeypatch.setattr(security, "get_session", fake_get_session)

    with pytest.raises(TelegramInitDataError, match="not allowed"):
        await security.authenticate_telegram_init_data(make_init_data(token))
