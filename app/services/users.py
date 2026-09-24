from __future__ import annotations

from aiogram.types import User as TelegramUser
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User
from app.db.repositories import sync_user


async def sync_telegram_user(
    session: AsyncSession,
    telegram_user: TelegramUser,
) -> tuple[User, bool]:
    return await sync_user(
        session,
        telegram_id=telegram_user.id,
        first_name=telegram_user.first_name,
        last_name=telegram_user.last_name,
        username=telegram_user.username,
        language_code=telegram_user.language_code,
        is_bot=telegram_user.is_bot,
    )


def format_user_profile(user: User) -> str:
    display_name = " ".join(
        part for part in (user.first_name, user.last_name) if part
    )

    username = f"@{user.username}" if user.username else "не указан"
    bio = user.bio or "не заполнено"
    city = user.city or "не указан"

    return (
        "👤 <b>Твой профиль</b>\n\n"
        f"<b>Имя:</b> {display_name}\n"
        f"<b>Username:</b> {username}\n"
        f"<b>Город:</b> {city}\n"
        f"<b>О себе:</b> {bio}\n\n"
        f"<b>ID:</b> <code>{user.telegram_id}</code>"
    )
