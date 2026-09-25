from __future__ import annotations

from fastapi import Header, HTTPException

from app.db.engine import get_session
from app.services.security import TelegramInitDataError, validate_telegram_init_data


async def get_current_telegram_user(
    x_telegram_init_data: str | None = Header(default=None, alias="X-Telegram-Init-Data"),
):
    if not x_telegram_init_data:
        raise HTTPException(status_code=401, detail="Telegram authentication required")

    try:
        payload = validate_telegram_init_data(x_telegram_init_data)
    except TelegramInitDataError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    async for session in get_session():
        from app.services.users import get_user_by_telegram_id
        user = await get_user_by_telegram_id(session, payload.user.id)
        if user is None:
            raise HTTPException(status_code=403, detail="Telegram user is not registered")
        if user.is_bot or not user.is_active:
            raise HTTPException(status_code=403, detail="User is not allowed")

    return user
