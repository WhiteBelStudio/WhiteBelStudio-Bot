from __future__ import annotations

from fastapi import Header, HTTPException
from collections.abc import AsyncIterator

from app.db.engine import get_session

from app.db.models import User
from app.services.security import (
    TelegramInitDataError,
    authenticate_telegram_init_data,
)


async def get_database_session() -> AsyncIterator:
    async for session in get_session():
        yield session


async def get_current_telegram_user(
    x_telegram_init_data: str | None = Header(
        default=None,
        alias="X-Telegram-Init-Data",
        description="Raw Telegram Mini App initData string.",
    ),
) -> User:
    """Resolve the request to the existing chat user from the shared database."""
    if not x_telegram_init_data:
        raise HTTPException(
            status_code=401,
            detail="Telegram authentication required",
        )

    try:
        return await authenticate_telegram_init_data(x_telegram_init_data)
    except TelegramInitDataError as exc:
        status_code = (
            403
            if str(exc) in {"Telegram user is not registered", "User is not allowed"}
            else 401
        )
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
