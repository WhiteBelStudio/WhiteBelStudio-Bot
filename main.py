"""WhiteBelStudio Bot entrypoint."""

from __future__ import annotations

import asyncio
import os

from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    BotCommand,
    BotCommandScopeDefault,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ErrorEvent,
    Message,
)

from app.db.engine import close_db, get_session
from app.db.health import check_database_connection
from app.bot.middleware import ChatReputationMiddleware
from app.bot.economy import router as economy_router
from app.bot.achievements import router as achievements_router
from app.bot.games import router as games_router
from app.services.community import (
    format_community_reputation,
    get_reputation_history,
    get_reputation_score,
    get_reputation_top,
)
from app.services.users import format_user_profile, sync_telegram_user

load_dotenv()


# Centralized fallback: individual handlers keep user-facing domain errors local;
# this catches unexpected exceptions so one update cannot terminate polling.
def _log_unhandled_error(event: ErrorEvent) -> None:
    print(f"[error] unhandled update error: {event.exception!r}", flush=True)


dp = Dispatcher()
dp.message.middleware(ChatReputationMiddleware())


@dp.error()
async def global_error_handler(event: ErrorEvent) -> bool:
    _log_unhandled_error(event)
    update = event.update
    if isinstance(update, CallbackQuery):
        try:
            await update.answer("⚠️ Произошла ошибка. Попробуй ещё раз.", show_alert=True)
        except Exception as exc:
            print(f"[error] callback error notification failed: {exc!r}", flush=True)
    elif isinstance(update, Message):
        try:
            await update.answer("⚠️ Произошла ошибка. Попробуй ещё раз.")
        except Exception as exc:
            print(f"[error] message error notification failed: {exc!r}", flush=True)
    return True

dp.include_router(economy_router)
dp.include_router(achievements_router)
dp.include_router(games_router)



@dp.message(CommandStart())
async def start_handler(message: Message) -> None:
    database_ok = False
    created = False

    if message.from_user is not None and os.getenv("DATABASE_URL", "").strip():
        try:
            async for session in get_session():
                _, created = await sync_telegram_user(session, message.from_user)
            database_ok = True
        except Exception as exc:
            print(f"[db] user sync failed: {exc}", flush=True)

    suffix = "\n\n🗄 База данных: подключена" if database_ok else ""
    account_status = "🆕 Аккаунт создан" if created else "♻️ Аккаунт обновлён"

    keyboard = InlineKeyboardMarkup(
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
        reply_markup=keyboard,
    )


@dp.callback_query(F.data.in_({
    "menu_profile",
    "menu_reputation",
    "menu_rules",
    "shop",
    "menu_help",
}))
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
        "🛑 /cancelgame — отменить активную мини-игру\n⚔️ /pvp — соревнование 1 на 1\n\n"
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


def help_categories_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="👤 Основные", callback_data="help_category:general"),
            ],
            [
                InlineKeyboardButton(text="🎮 Игровые", callback_data="help_category:game"),
                InlineKeyboardButton(text="🛡 Модерация", callback_data="help_category:moderation"),
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

@dp.callback_query(F.data == "help_categories")
async def help_categories_callback(callback: CallbackQuery) -> None:
    if callback.message is not None:
        await show_help_categories(callback.message, edit=True)
    await callback.answer()


@dp.callback_query(F.data.startswith("help_category:"))
async def help_category_callback(callback: CallbackQuery) -> None:
    category = (callback.data or "").split(":", 1)[1]
    if callback.message is not None:
        await show_help_category(callback.message, category)
    await callback.answer()


@dp.message(Command("help"))
async def help_handler(message: Message) -> None:
    await show_help_categories(message)


@dp.message(Command("rules"))
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


@dp.message(Command("rep"))
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
        print(f"[reputation] load failed: {exc}", flush=True)
        await message.answer("⚠️ Не удалось загрузить репутацию.")


@dp.message(Command("toprep"))
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
        print(f"[reputation] top failed: {exc}", flush=True)
        await message.answer("⚠️ Не удалось загрузить топ.")



@dp.message(Command("profile"))
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
        print(f"[db] profile load failed: {exc}", flush=True)
        await message.answer("⚠️ Не удалось загрузить профиль. Попробуй ещё раз.")


async def setup_bot_commands(bot: Bot) -> None:
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


async def main() -> None:
    token = os.environ.get("BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("BOT_TOKEN is not set in .env")

    proxy = os.getenv("TELEGRAM_PROXY", "").strip() or None
    session = AiohttpSession(proxy=proxy)

    bot = Bot(
        token=token,
        session=session,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    print("========================================", flush=True)
    print(" WhiteBelStudio Bot", flush=True)
    print("========================================", flush=True)
    print(f"[bot] Telegram proxy: {'enabled' if proxy else 'disabled'}", flush=True)

    if os.getenv("DATABASE_URL", "").strip():
        try:
            await check_database_connection()
            print("[db] PostgreSQL: OK", flush=True)
        except Exception as exc:
            print(f"[db] PostgreSQL: unavailable ({exc})", flush=True)
    else:
        print("[db] DATABASE_URL: not configured", flush=True)

    try:
        await setup_bot_commands(bot)
        print("[bot] Command menu: configured", flush=True)
        print("[bot] Starting polling...", flush=True)
        await dp.start_polling(bot)
    finally:
        await close_db()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())