from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.db.engine import get_session
from app.services.achievements import (
    ACHIEVEMENTS,
    get_achievement_progress,
    list_user_achievements,
)
from app.services.users import sync_telegram_user

router = Router()

_METRIC_LABELS = {
    "games": "🎮 Игры",
    "wins": "🏆 Победы",
    "losses": "💠 Испытания",
    "draws": "🤝 Ничьи",
    "level": "⭐ Уровни",
    "xp": "✨ XP",
    "messages": "💬 Общение",
    "conversations": "🤝 Диалоги",
    "reputation": "🛡️ Репутация",
    "rep_voters": "🛡️ Репутация от людей",
    "balance": "💰 Экономика",
    "lifetime_earned": "💰 Заработок",
    "lifetime_spent": "🛍️ Расходы",
    "transactions": "💳 Операции",
    "pvp_matches": "⚔️ PvP",
    "pvp_wins": "⚔️ PvP победы",
    "pvp_opponents": "⚔️ PvP соперники",
    "active_days": "📅 Активность",
    "multi_games_wins": "🎯 Комбинированные",
    "social_gamer": "🎯 Комбинированные",
    "gamer_rep": "🎯 Комбинированные",
    "rich_gamer": "🎯 Комбинированные",
    "pvp_social": "🎯 Комбинированные",
    "earned_achievements": "🏅 Коллекция",
}

@router.message(Command("achievements"))
async def achievements_handler(message: Message) -> None:
    if message.from_user is None:
        return
    try:
        async for session in get_session():
            user, _ = await sync_telegram_user(session, message.from_user)
            earned, locked = await list_user_achievements(session, user.id)
            progress = await get_achievement_progress(session, user.id)

        earned_codes = {item.code for item in earned}
        lines = [
            "🏆 <b>Достижения</b>",
            f"📊 Прогресс: <b>{len(earned)}/100</b>",
            "",
        ]

        current_category = None
        for item in ACHIEVEMENTS:
            category = _METRIC_LABELS.get(item.metric, "🎯 Специальные")
            if category != current_category:
                current_category = category
                lines.extend(["", f"<b>{category}</b>"])
            value, target = progress[item.code]
            icon = "✅" if item.code in earned_codes else "🔒"
            lines.append(f"{icon} {item.name} — {value}/{target}")

        await message.answer("\n".join(lines))
    except Exception as exc:
        print(f"[achievements] failed: {exc}", flush=True)
        await message.answer("⚠️ Не удалось загрузить достижения.")
