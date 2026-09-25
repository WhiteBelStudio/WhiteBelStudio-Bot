from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import Message

from app.db.engine import get_session
from app.services.community import (
    format_community_reputation,
    get_reputation_history,
    get_reputation_score,
    get_reputation_top,
    set_chat_reputation_vote,
)
from app.services.social import get_user_by_username
from app.services.users import sync_telegram_user


async def _handle_group_reputation(message: Message) -> bool:
    if message.chat.type not in {"group", "supergroup"} or message.from_user is None:
        return False

    text = (message.text or "").strip()
    parts = text.split()
    if not parts:
        return False

    command = parts[0].split("@", 1)[0].lower()
    if command not in {"/rep", "/rep+", "/rep-", "/toprep"}:
        return False

    async for session in get_session():
        actor, _ = await sync_telegram_user(session, message.from_user)

        from app.services.chat import get_or_create_chat
        chat = await get_or_create_chat(
            session,
            message.chat.id,
            message.chat.title or "Без названия",
            message.chat.type,
        )

        if command == "/toprep":
            rows = await get_reputation_top(session, 10, chat.id)
            if not rows:
                await message.answer("🏆 В этом чате пока нет репутации.")
                return True
            lines = ["🏆 <b>Топ репутации этого чата</b>", ""]
            for index, (_, name, score) in enumerate(rows, 1):
                lines.append(f"{index}. {name} — <b>{score}</b>")
            await message.answer("\n".join(lines))
            return True

        target = None
        if message.reply_to_message and message.reply_to_message.from_user:
            target = message.reply_to_message.from_user
        elif len(parts) > 1:
            target = await get_user_by_username(session, parts[1].lstrip("@"))
            if target is None:
                await message.answer("❌ Пользователь с таким username не найден.")
                return True

        if target is None:
            score = await get_reputation_score(session, actor.id, chat.id)
            history = await get_reputation_history(session, actor.id, 10, chat.id)
            name = " ".join(p for p in (actor.first_name, actor.last_name) if p) or "Участник"
            await message.answer(format_community_reputation(name, score, history))
            return True

        target_user, _ = await sync_telegram_user(session, target)
        if target_user.id == actor.id:
            await message.answer("🙂 Нельзя изменять собственную репутацию.")
            return True

        if command == "/rep":
            score = await get_reputation_score(session, target_user.id, chat.id)
            history = await get_reputation_history(session, target_user.id, 10, chat.id)
            name = " ".join(p for p in (target_user.first_name, target_user.last_name) if p) or "Участник"
            await message.answer(format_community_reputation(name, score, history))
            return True

        vote = 1 if command == "/rep+" else -1
        try:
            changed, score = await set_chat_reputation_vote(
                session, chat.id, actor.id, target_user.id, vote
            )
        except ValueError as exc:
            messages = {
                "rater_not_allowed": "❌ Твой аккаунт не может изменять репутацию.",
                "rated_not_allowed": "❌ Этому аккаунту нельзя изменять репутацию.",
                "user_not_found": "❌ Пользователь не найден.",
            }
            await message.answer(messages.get(str(exc), "⚠️ Не удалось изменить репутацию."))
            return True
        if not changed:
            await message.answer("ℹ️ Ты уже поставил такую оценку этому участнику.")
            return True

        sign = "+1 ⭐" if vote > 0 else "-1 ⭐"
        name = " ".join(p for p in (target_user.first_name, target_user.last_name) if p) or "Участник"
        await message.answer(f"{sign} <b>{name}</b>\nРепутация в этом чате: <b>{score}</b>")
        return True

    return True


class ChatReputationMiddleware(BaseMiddleware):
    """Handle only chat reputation commands; no chat activity tracking."""

    async def __call__(
        self,
        handler: Callable[[Message, dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: dict[str, Any],
    ) -> Any:
        try:
            if await _handle_group_reputation(event):
                return None
        except Exception as exc:
            print(f"[reputation] command failed: {exc}", flush=True)
        return await handler(event, data)
