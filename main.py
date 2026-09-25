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
from app.services.social import (
    find_users,
    format_social_user,
    get_user_by_username,
    list_friends,
    list_incoming_requests,
    remove_friend,
    respond_to_request,
    send_friend_request,
)
from app.services.users import format_user_profile, sync_telegram_user

load_dotenv()


dp = Dispatcher()
dp.message.middleware(ChatReputationMiddleware())
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
    "social": (
        "👥 <b>Социальные команды</b>\n\n"
        "🔎 /find [запрос] — найти участника\n"
        "👥 /friends — список друзей\n"
        "📨 /requests — входящие заявки в друзья\n"
        "➕ /addfriend @username — отправить заявку\n"
        "✅ /accept @username — принять заявку\n"
        "❌ /decline @username — отклонить заявку\n"
        "🗑 /removefriend @username — удалить из друзей"
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
                InlineKeyboardButton(text="👥 Социальные", callback_data="help_category:social"),
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


@dp.message(Command("find"))
async def find_handler(message: Message) -> None:
    if message.from_user is None:
        return

    query = (message.text or "").split(maxsplit=1)
    search = query[1].strip() if len(query) > 1 else None

    try:
        async for session in get_session():
            current, _ = await sync_telegram_user(session, message.from_user)
            users = await find_users(session, current.id, search)

        if not users:
            await message.answer("🔎 Никого не нашёл. Попробуй другой запрос.")
            return

        lines = ["🔎 <b>Люди</b>", ""]
        for user in users:
            lines.append(format_social_user(user))
        lines.append("")
        lines.append("Чтобы отправить заявку: <code>/addfriend @username</code>")
        await message.answer("\n".join(lines))
    except Exception as exc:
        print(f"[social] find failed: {exc}", flush=True)
        await message.answer("⚠️ Не удалось выполнить поиск.")


@dp.message(Command("addfriend"))
async def add_friend_handler(message: Message) -> None:
    if message.from_user is None:
        return

    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        await message.answer("Использование: <code>/addfriend @username</code>")
        return

    username = parts[1].strip().split()[0]

    try:
        async for session in get_session():
            sender, _ = await sync_telegram_user(session, message.from_user)
            target = await get_user_by_username(session, username)

            if target is None:
                result = "not_found"
            else:
                result = await send_friend_request(session, sender.id, target.id)

        responses = {
            "not_found": "❌ Пользователь не найден.",
            "self": "🙂 Нельзя добавить самого себя.",
            "unavailable": "❌ Пользователь недоступен.",
            "friends": "👥 Вы уже друзья.",
            "outgoing": "📨 Заявка уже отправлена.",
            "incoming": "📨 Этот пользователь уже отправил тебе заявку. Используй /requests.",
            "created": "✅ Заявка в друзья отправлена.",
        }
        await message.answer(responses.get(result, "⚠️ Не удалось отправить заявку."))
    except Exception as exc:
        print(f"[social] add friend failed: {exc}", flush=True)
        await message.answer("⚠️ Не удалось отправить заявку.")


@dp.message(Command("requests"))
async def requests_handler(message: Message) -> None:
    if message.from_user is None:
        return

    try:
        async for session in get_session():
            current, _ = await sync_telegram_user(session, message.from_user)
            requests = await list_incoming_requests(session, current.id)

        if not requests:
            await message.answer("📨 Новых заявок в друзья нет.")
            return

        lines = ["📨 <b>Заявки в друзья</b>", ""]
        for _, user in requests:
            name = " ".join(p for p in (user.first_name, user.last_name) if p)
            username = f"@{user.username}" if user.username else "без username"
            lines.append(f"👤 <b>{name}</b> — {username}")
        lines.extend([
            "",
            "Принять: <code>/accept @username</code>",
            "Отклонить: <code>/decline @username</code>",
        ])
        await message.answer("\n".join(lines))
    except Exception as exc:
        print(f"[social] requests failed: {exc}", flush=True)
        await message.answer("⚠️ Не удалось загрузить заявки.")


@dp.message(Command("accept"))
async def accept_handler(message: Message) -> None:
    await _respond_to_request(message, True)


@dp.message(Command("decline"))
async def decline_handler(message: Message) -> None:
    await _respond_to_request(message, False)


async def _respond_to_request(message: Message, accept: bool) -> None:
    if message.from_user is None:
        return

    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Укажи username: <code>/accept @username</code>")
        return

    try:
        async for session in get_session():
            current, _ = await sync_telegram_user(session, message.from_user)
            sender = await get_user_by_username(session, parts[1].strip().split()[0])
            if sender is None:
                result = "missing"
            else:
                result = await respond_to_request(session, current.id, sender.id, accept)

        if result == "missing":
            await message.answer("❌ Такая заявка не найдена.")
        elif accept:
            await message.answer("🤝 Заявка принята. Теперь вы друзья!")
        else:
            await message.answer("❌ Заявка отклонена.")
    except Exception as exc:
        print(f"[social] request response failed: {exc}", flush=True)
        await message.answer("⚠️ Не удалось обработать заявку.")


@dp.message(Command("friends"))
async def friends_handler(message: Message) -> None:
    if message.from_user is None:
        return

    try:
        async for session in get_session():
            current, _ = await sync_telegram_user(session, message.from_user)
            friends = await list_friends(session, current.id)

        if not friends:
            await message.answer("👥 Друзей пока нет. Используй /find.")
            return

        lines = ["👥 <b>Твои друзья</b>", ""]
        for user in friends:
            lines.append(format_social_user(user))
        lines.extend(["", "Удалить: <code>/removefriend @username</code>"])
        await message.answer("\n".join(lines))
    except Exception as exc:
        print(f"[social] friends failed: {exc}", flush=True)
        await message.answer("⚠️ Не удалось загрузить список друзей.")


@dp.message(Command("removefriend"))
async def remove_friend_handler(message: Message) -> None:
    if message.from_user is None:
        return

    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Использование: <code>/removefriend @username</code>")
        return

    try:
        async for session in get_session():
            current, _ = await sync_telegram_user(session, message.from_user)
            target = await get_user_by_username(session, parts[1].strip().split()[0])
            removed = False if target is None else await remove_friend(session, current.id, target.id)

        await message.answer(
            "✅ Пользователь удалён из друзей." if removed else "❌ Такого друга нет."
        )
    except Exception as exc:
        print(f"[social] remove friend failed: {exc}", flush=True)
        await message.answer("⚠️ Не удалось удалить друга.")




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
            BotCommand(command="find", description="Найти участника"),
            BotCommand(command="friends", description="Друзья"),
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