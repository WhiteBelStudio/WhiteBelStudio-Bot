"""Core Telegram commands and navigation for WhiteBelStudio."""

from __future__ import annotations

import logging
import os

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    BotCommand,
    BotCommandScopeDefault,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from app.db.engine import get_session
from app.services.community import (
    format_community_reputation,
    get_reputation_history,
    get_reputation_score,
    get_reputation_top,
)
from app.services.users import format_user_profile, sync_telegram_user

LOGGER = logging.getLogger("bot.core")
router = Router(name="core")

HELP_CATEGORIES = {
    "general": (
        "👤 <b>Основные команды</b>\n\n"
        "👤 /profile — посмотреть свой профиль\n"
        "⭐ /rep — посмотреть свою репутацию\n"
        "➕ /rep+ — положительная оценка участнику (в группе)\n"
        "➖ /rep- — отрицательная оценка участнику (в группе)\n"
        "🏆 /toprep — топ участников по репутации\n"
        "📜 /rules — правила сообщества"
    ),
    "game": (
        "🎮 <b>Игровые команды</b>\n\n"
        "🎮 /game — игровой профиль\n"
        "🏆 /gametop — топ игроков\n"
        "🕹 /games — мини-игры\n"
        "🛑 /cancelgame — отменить активную мини-игру\n"
        "⚔️ /pvp — соревнование 1 на 1\n\n"
        "🪙 /balance — баланс монет\n"
        "🎁 /daily — ежедневная награда\n"
        "🛒 /shop — магазин\n"
        "📦 /inventory — мои предметы\n"
        "📜 /coinhistory — история монет\n"
        "🎁 /gift @username ID — подарить подарок"
    ),
    "moderation": (
        "🛡 <b>Модерация</b>\n\n"
        "Раздел модерации предназначен для администраторов и модераторов.\n"
        "Если у тебя есть права, используй доступные административные команды из панели бота."
    ),
}


def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="👤 Профиль", callback_data="menu_profile"),
                InlineKeyboardButton(text="⭐ Репутация", callback_data="menu_reputation"),
            ],
            [
                InlineKeyboardButton(text="📜 Правила", callback_data="menu_rules"),
                InlineKeyboardButton(text="🛒 Магазин", callback_data="shop"),
                InlineKeyboardButton(text="❓ Помощь", callback_data="menu_help"),
            ],
            [
                InlineKeyboardButton(text="⚔️ PvP", callback_data="games:pvp"),
                InlineKeyboardButton(text="🎮 Мини-игры", callback_data="games:mini"),
            ],
        ]
    )


def help_categories_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="👤 Основные", callback_data="help_category:general")],
            [
                InlineKeyboardButton(text="🎮 Игровые", callback_data="help_category:game"),
                InlineKeyboardButton(
                    text="🛡 Модерация", callback_data="help_category:moderation"
                ),
            ],
        ]
    )


def help_back_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ К категориям", callback_data="help_categories")]
        ]
    )


async def show_help_categories(message: Message, *, edit: bool = False) -> None:
    text = (
        "❓ <b>Помощь WhiteBelStudio</b>\n\n"
        "Выбери категорию команд, чтобы посмотреть доступные команды и краткие гайды."
    )
    if edit:
        await message.edit_text(text, reply_markup=help_categories_keyboard())
    else:
        await message.answer(text, reply_markup=help_categories_keyboard())


async def show_help_category(message: Message, category: str) -> None:
    content = HELP_CATEGORIES.get(category)
    if content is None:
        await message.answer("⚠️ Категория помощи не найдена.")
        return
    await message.edit_text(content, reply_markup=help_back_keyboard())


@router.message(CommandStart())
async def start_handler(message: Message) -> None:
    database_ok = False
    created = False

    if message.from_user is not None and os.getenv("DATABASE_URL", "").strip():
        try:
            async for session in get_session():
                _, created = await sync_telegram_user(session, message.from_user)
            database_ok = True
        except Exception as exc:
            LOGGER.exception("user_sync_failed", exc_info=exc)

    suffix = "\n\n🗄 База данных: подключена" if database_ok else ""
    account_status = "🆕 Аккаунт создан" if created else "♻️ Аккаунт обновлён"

    await message.answer(
        "👋 Привет!\n\n"
        "Добро пожаловать в WhiteBelStudio.\n"
        f"{account_status}\n\n"
        "👤 /profile — профиль\n"
        "⭐ /rep — твоя репутация\n"
        "🏆 /toprep — топ участников\n"
        "📜 /rules — правила\n"
        "❓ /help — помощь"
        + suffix,
        reply_markup=main_menu_keyboard(),
    )


@router.callback_query(
    F.data.in_({"menu_profile", "menu_reputation", "menu_rules", "shop", "menu_help"})
)
async def menu_callback_handler(callback: CallbackQuery) -> None:
    if callback.message is None:
        await callback.answer()
        return

    action = callback.data or ""
    if action == "menu_profile":
        await profile_handler(callback.message)
    elif action == "menu_reputation":
        await rep_handler(callback.message)
    elif action == "menu_rules":
        await rules_handler(callback.message)
    elif action == "shop":
        from app.bot.economy import show_shop
        await show_shop(callback.message, edit=True)
    elif action == "menu_help":
        await show_help_categories(callback.message, edit=True)
    await callback.answer()


@router.callback_query(F.data == "help_categories")
async def help_categories_callback(callback: CallbackQuery) -> None:
    if callback.message is not None:
        await show_help_categories(callback.message, edit=True)
    await callback.answer()


@router.callback_query(F.data.startswith("help_category:"))
async def help_category_callback(callback: CallbackQuery) -> None:
    category = (callback.data or "").split(":", 1)[1]
    if callback.message is not None:
        await show_help_category(callback.message, category)
    await callback.answer()


@router.message(Command("help"))
async def help_handler(message: Message) -> None:
    await show_help_categories(message)


@router.message(Command("rules"))
async def rules_handler(message: Message) -> None:
    await message.answer(
        "📜 <b>Правила сообщества</b>\n\n"
        "1. Уважай других участников.\n"
        "2. Не спамь и не флуди.\n"
        "3. Не публикуй запрещённый или опасный контент.\n"
        "4. Не выдавай себя за другого участника.\n"
        "5. Выполняй требования модераторов.\n\n"
        "Нарушения могут влиять на репутацию и приводить к ограничениям."
    )


@router.message(Command("rep"))
async def rep_handler(message: Message) -> None:
    if message.from_user is None:
        return
    try:
        async for session in get_session():
            user, _ = await sync_telegram_user(session, message.from_user)
            score = await get_reputation_score(session, user.id)
            history = await get_reputation_history(session, user.id)
        name = " ".join(p for p in (user.first_name, user.last_name) if p)
        await message.answer(format_community_reputation(name, score, history))
    except Exception as exc:
        LOGGER.exception("reputation_load_failed", exc_info=exc)
        await message.answer("⚠️ Не удалось загрузить репутацию.")


@router.message(Command("toprep"))
async def top_rep_handler(message: Message) -> None:
    try:
        async for session in get_session():
            rows = await get_reputation_top(session, 10)
        if not rows:
            await message.answer("🏆 Пока нет участников с изменениями репутации.")
            return
        lines = ["🏆 <b>Топ репутации</b>", ""]
        for index, (_, name, score) in enumerate(rows, 1):
            lines.append(f"{index}. {name} — <b>{score}</b>")
        await message.answer("\n".join(lines))
    except Exception as exc:
        LOGGER.exception("reputation_top_failed", exc_info=exc)
        await message.answer("⚠️ Не удалось загрузить топ.")


@router.message(Command("profile"))
async def profile_handler(message: Message) -> None:
    if message.from_user is None:
        return
    if not os.getenv("DATABASE_URL", "").strip():
        await message.answer("🗄 База данных пока не настроена.")
        return
    try:
        async for session in get_session():
            user, _ = await sync_telegram_user(session, message.from_user)
            text = format_user_profile(user)
        await message.answer(text)
    except Exception as exc:
        LOGGER.exception("profile_load_failed", exc_info=exc)
        await message.answer("⚠️ Не удалось загрузить профиль. Попробуй ещё раз.")


async def setup_bot_commands(bot) -> None:
    await bot.set_my_commands(
        [
            BotCommand(command="start", description="Открыть меню"),
            BotCommand(command="help", description="Помощь"),
            BotCommand(command="game", description="Игровой профиль"),
            BotCommand(command="gametop", description="Топ игроков"),
            BotCommand(command="achievements", description="Мои достижения"),
            BotCommand(command="games", description="Игры: PvP и мини-игры"),
            BotCommand(command="pvp", description="PvP-соревнования"),
            BotCommand(command="balance", description="Баланс монет"),
            BotCommand(command="daily", description="Ежедневная награда"),
            BotCommand(command="shop", description="Магазин"),
            BotCommand(command="inventory", description="Мои предметы"),
            BotCommand(command="coinhistory", description="История монет"),
            BotCommand(command="gift", description="Подарить предмет"),
            BotCommand(command="profile", description="Мой профиль"),
            BotCommand(command="rep", description="Моя репутация"),
            BotCommand(command="toprep", description="Топ репутации"),
            BotCommand(command="rules", description="Правила сообщества"),
        ],
        scope=BotCommandScopeDefault(),
    )
