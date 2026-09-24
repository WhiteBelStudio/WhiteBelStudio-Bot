from __future__ import annotations

from collections.abc import Awaitable, Callable
import os
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import Message

from app.db.engine import get_session
from app.services.chat import record_chat_activity
from app.services.users import sync_telegram_user


def is_trackable_community_message(message: Message) -> bool:
    return (
        message.chat.type in {"group", "supergroup"}
        and message.from_user is not None
        and not message.from_user.is_bot
        and bool(os.getenv("DATABASE_URL", "").strip())
    )


class ChatActivityMiddleware(BaseMiddleware):
    """Record group activity before command handlers consume the update."""

    async def __call__(
        self,
        handler: Callable[[Message, dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: dict[str, Any],
    ) -> Any:
        if is_trackable_community_message(event):
            try:
                async for session in get_session():
                    user, _ = await sync_telegram_user(session, event.from_user)
                    await record_chat_activity(
                        session,
                        event.chat.id,
                        event.chat.title or "Без названия",
                        event.chat.type,
                        user,
                        is_command=bool((event.text or "").lstrip().startswith("/")),
                    )
            except Exception as exc:
                print(f"[chat] activity middleware failed: {exc}", flush=True)

        return await handler(event, data)
