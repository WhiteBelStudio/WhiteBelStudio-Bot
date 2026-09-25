from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass
from urllib.parse import parse_qsl

from aiogram.types import User as TelegramUser

from app.db.engine import get_session
from app.db.models import User
from app.services.users import get_user_by_telegram_id


class TelegramInitDataError(ValueError):
    """Raised when Telegram Mini App initData is invalid."""


@dataclass(frozen=True, slots=True)
class TelegramInitData:
    user: TelegramUser
    auth_date: int
    query_id: str | None


def _bot_token() -> str:
    token = os.getenv("BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("BOT_TOKEN is not set")
    return token


def validate_telegram_init_data(
    init_data: str,
    *,
    now: int | None = None,
    max_age_seconds: int = 86400,
) -> TelegramInitData:
    if not init_data or len(init_data) > 8192:
        raise TelegramInitDataError("Invalid initData")

    values = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = values.pop("hash", "")
    if not received_hash or len(received_hash) != 64:
        raise TelegramInitDataError("Invalid initData")

    data_check_string = "\n".join(
        f"{key}={value}" for key, value in sorted(values.items())
    )
    secret_key = hmac.new(
        b"WebAppData",
        _bot_token().encode("utf-8"),
        hashlib.sha256,
    ).digest()
    expected_hash = hmac.new(
        secret_key,
        data_check_string.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(expected_hash, received_hash):
        raise TelegramInitDataError("Invalid initData")

    try:
        auth_date = int(values["auth_date"])
        user_payload = json.loads(values["user"])
        telegram_user = TelegramUser.model_validate(user_payload)
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise TelegramInitDataError("Invalid initData") from exc

    current_time = int(time.time()) if now is None else now
    if auth_date > current_time + 60 or current_time - auth_date > max_age_seconds:
        raise TelegramInitDataError("Expired initData")

    return TelegramInitData(
        user=telegram_user,
        auth_date=auth_date,
        query_id=values.get("query_id"),
    )


async def authenticate_telegram_init_data(init_data: str) -> User:
    payload = validate_telegram_init_data(init_data)
    async for session in get_session():
        user = await get_user_by_telegram_id(session, payload.user.id)
        if user is None:
            raise TelegramInitDataError("Telegram user is not registered")
        if user.is_bot or not user.is_active:
            raise TelegramInitDataError("User is not allowed")
        return user
    raise TelegramInitDataError("Authentication failed")
