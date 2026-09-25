from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.db.engine import get_session
from app.services.achievements import list_user_achievements
from app.services.users import sync_telegram_user


router = Router()


@router.message(Command("achievements"))
async def achievements_handler(message: Message) -> None:
    if message.from_user is None:
        return
    try:
        async for session in get_session():
            user, _ = await sync_telegram_user(session, message.from_user)
            earned, locked = await list_user_achievements(session, user.id)

        lines = ["🏆 <b>Достижения</b>", ""]
        if earned:
            lines.append(f"✅ Получено: <b>{len(earned)}</b>")
            for item in earned:
                lines.append(f"• {item.name} — {item.description}")
        else:
            lines.append("Пока нет открытых достижений.")

        if locked:
            lines.extend(["", f"🔒 Впереди: <b>{len(locked)}</b>"])
            for item in locked:
                lines.append(f"• {item.name} — {item.description}")

        await message.answer("\n".join(lines))
    except Exception as exc:
        print(f"[achievements] failed: {exc}", flush=True)
        await message.answer("⚠️ Не удалось загрузить достижения.")
