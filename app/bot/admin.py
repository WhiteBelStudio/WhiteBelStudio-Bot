"""Protected owner-only administrative Telegram panel."""

from __future__ import annotations

import logging
import os

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import func, select

from app.db.engine import get_session
from app.db.models import CommunityChat, Conversation, MessageRecord, User

LOGGER = logging.getLogger("bot.admin")
router = Router(name="admin")


def _owner_id() -> int | None:
    raw = os.getenv("OWNER_ID", "").strip()
    try:
        return int(raw) if raw else None
    except ValueError:
        LOGGER.error("invalid_owner_id")
        return None


def is_admin(telegram_id: int | None) -> bool:
    owner_id = _owner_id()
    return telegram_id is not None and owner_id is not None and telegram_id == owner_id


def admin_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📊 Статистика", callback_data="admin:stats"),
                InlineKeyboardButton(text="🩺 Состояние", callback_data="admin:health"),
            ],
            [
                InlineKeyboardButton(text="👤 Пользователь", callback_data="admin:user_help"),
                InlineKeyboardButton(text="❌ Закрыть", callback_data="admin:close"),
            ],
        ]
    )


async def _stats_text() -> str:
    async for session in get_session():
        users = int((await session.execute(select(func.count(User.id)))).scalar_one() or 0)
        active = int(
            (
                await session.execute(
                    select(func.count(User.id)).where(
                        User.is_active.is_(True), User.is_bot.is_(False)
                    )
                )
            ).scalar_one()
            or 0
        )
        chats = int((await session.execute(select(func.count(CommunityChat.id)))).scalar_one() or 0)
        conversations = int(
            (await session.execute(select(func.count(Conversation.id)))).scalar_one() or 0
        )
        messages = int(
            (await session.execute(select(func.count(MessageRecord.id)))).scalar_one() or 0
        )
    return (
        "📊 <b>Статистика WhiteBelStudio</b>\n\n"
        f"👤 Пользователей: <b>{users}</b>\n"
        f"🟢 Активных участников: <b>{active}</b>\n"
        f"💬 Чатов: <b>{chats}</b>\n"
        f"🤝 Диалогов: <b>{conversations}</b>\n"
        f"✉️ Сообщений: <b>{messages}</b>"
    )


def _health_text() -> str:
    return (
        "🩺 <b>Состояние системы</b>\n\n"
        f"🗄 DATABASE_URL: <b>{'настроен' if os.getenv('DATABASE_URL', '').strip() else 'не настроен'}</b>\n"
        f"👑 OWNER_ID: <b>{'настроен' if _owner_id() is not None else 'не настроен'}</b>\n"
        f"🤖 BOT_TOKEN: <b>{'настроен' if os.getenv('BOT_TOKEN', '').strip() else 'не настроен'}</b>"
    )


@router.message(Command("admin"))
async def admin_command(message: Message) -> None:
    if not is_admin(message.from_user.id if message.from_user else None):
        await message.answer("⛔ Доступ к административной панели запрещён.")
        return
    try:
        await message.answer(
            "🛡 <b>Административная панель</b>\n\nВыбери нужный раздел.",
            reply_markup=admin_menu_keyboard(),
        )
    except Exception as exc:
        LOGGER.exception("admin_menu_failed", exc_info=exc)
        await message.answer("⚠️ Не удалось открыть административную панель.")


@router.callback_query(F.data.startswith("admin:"))
async def admin_callback(callback: CallbackQuery) -> None:
    if not is_admin(callback.from_user.id if callback.from_user else None):
        await callback.answer("⛔ Доступ запрещён.", show_alert=True)
        return
    if callback.message is None:
        await callback.answer()
        return

    action = (callback.data or "").split(":", 1)[1]
    try:
        if action == "stats":
            await callback.message.edit_text(await _stats_text(), reply_markup=admin_menu_keyboard())
        elif action == "health":
            await callback.message.edit_text(_health_text(), reply_markup=admin_menu_keyboard())
        elif action == "user_help":
            await callback.message.edit_text(
                "👤 <b>Поиск пользователя</b>\n\n"
                "Используй:\n<code>/admin_user 123456789</code>\n"
                "или\n<code>/admin_user @username</code>",
                reply_markup=admin_menu_keyboard(),
            )
        elif action == "close":
            await callback.message.edit_text("🛡 Административная панель закрыта.")
        else:
            await callback.answer("⚠️ Неизвестный раздел.", show_alert=True)
            return
        await callback.answer()
    except Exception as exc:
        LOGGER.exception("admin_callback_failed", exc_info=exc)
        await callback.answer("⚠️ Ошибка панели.", show_alert=True)


@router.message(Command("admin_user"))
async def admin_user_command(message: Message) -> None:
    if not is_admin(message.from_user.id if message.from_user else None):
        await message.answer("⛔ Доступ к административной панели запрещён.")
        return

    parts = (message.text or "").split(maxsplit=1)
    if len(parts) != 2:
        await message.answer(
            "ℹ️ Использование: <code>/admin_user ID</code> или "
            "<code>/admin_user @username</code>"
        )
        return

    value = parts[1].strip().lstrip("@")
    try:
        async for session in get_session():
            if value.isdigit():
                user = (
                    await session.execute(select(User).where(User.telegram_id == int(value)))
                ).scalar_one_or_none()
            else:
                user = (
                    await session.execute(select(User).where(User.username.ilike(value)))
                ).scalar_one_or_none()

        if user is None:
            await message.answer("❌ Пользователь не найден.")
            return

        name = " ".join(p for p in (user.first_name, user.last_name) if p) or "Без имени"
        username = f"@{user.username}" if user.username else "не указан"
        await message.answer(
            "👤 <b>Пользователь</b>\n\n"
            f"Имя: <b>{name}</b>\n"
            f"Username: <b>{username}</b>\n"
            f"Telegram ID: <code>{user.telegram_id}</code>\n"
            f"Статус: <b>{'активен' if user.is_active else 'неактивен'}</b>\n"
            f"Бот: <b>{'да' if user.is_bot else 'нет'}</b>\n"
            f"Регистрация: <code>{user.created_at}</code>"
        )
    except Exception as exc:
        LOGGER.exception("admin_user_lookup_failed", exc_info=exc)
        await message.answer("⚠️ Не удалось выполнить поиск пользователя.")
