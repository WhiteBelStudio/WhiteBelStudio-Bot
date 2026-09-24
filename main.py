"""WhiteBelStudio Bot entrypoint."""

from __future__ import annotations

import asyncio
import os

from dotenv import load_dotenv

from aiogram import Bot, Dispatcher
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
from app.services.chat import get_chat_stats, get_member_stats, record_chat_activity
from app.services.community import format_community_reputation, get_reputation_history, get_reputation_score, get_reputation_top
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
                InlineKeyboardButton(text="❓ Помощь", callback_data="menu_help"),
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


@dp.callback_query()
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
    elif action == "menu_help":
        await help_handler(callback.message)

    await callback.answer()


@dp.message(Command("chatstats"))
async def chat_stats_handler(message: Message) -> None:
    if message.chat.type not in {"group", "supergroup"}:
        await message.answer("ℹ️ Эта команда работает внутри группового чата.")
        return

    if not os.getenv("DATABASE_URL", "").strip():
        await message.answer("🗄 База данных пока не настроена.")
        return

    try:
        async for session in get_session():
            chat, members, messages = await get_chat_stats(
                session,
                message.chat.id,
            )

        if chat is None:
            await message.answer("📊 Статистика пока пустая. Начни общаться в чате.")
            return

        await message.answer(
            f"📊 <b>Статистика чата</b>\n\n"
            f"💬 {chat.title}\n"
            f"👥 Участников в статистике: <b>{members}</b>\n"
            f"📝 Сообщений: <b>{messages}</b>"
        )
    except Exception as exc:
        print(f"[chat] stats failed: {exc}", flush=True)
        await message.answer("⚠️ Не удалось загрузить статистику чата.")


@dp.message(Command("mystats"))
async def my_stats_handler(message: Message) -> None:
    if message.chat.type not in {"group", "supergroup"} or message.from_user is None:
        await message.answer("ℹ️ Эта команда работает внутри группового чата.")
        return

    if not os.getenv("DATABASE_URL", "").strip():
        await message.answer("🗄 База данных пока не настроена.")
        return

    try:
        async for session in get_session():
            user, _ = await sync_telegram_user(session, message.from_user)
            stats = await get_member_stats(session, message.chat.id, user.id)

        if stats is None:
            await message.answer("📊 Ты пока не отмечен в статистике этого чата.")
            return

        await message.answer(
            f"📈 <b>Твоя активность</b>\n\n"
            f"💬 Сообщений: <b>{stats.message_count}</b>\n"
            f"🤖 Команд: <b>{stats.command_count}</b>"
        )
    except Exception as exc:
        print(f"[chat] member stats failed: {exc}", flush=True)
        await message.answer("⚠️ Не удалось загрузить твою статистику.")


@dp.message(Command("help"))
async def help_handler(message: Message) -> None:
    await message.answer(
        "❓ <b>WhiteBelStudio</b>\n\n"
        "🤖 Я бот-модератор и помощник сообщества.\n\n"
        "👤 /profile — профиль\n"
        "⭐ /rep — твоя репутация\n"
        "🏆 /toprep — участники с высокой репутацией\n"
        "📜 /rules — правила\n"
        "🔎 /find — поиск участников\n"
        "👥 /friends — друзья\n"
        "📊 /chatstats — статистика чата\n"
        "📈 /mystats — моя активность\n\n"
        "Модерационные команды доступны администраторам."
    )


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
            from sqlalchemy import func, select
            from app.db.models import User
            from app.services.community import ReputationEvent

            result = await session.execute(
                select(
                    User,
                    func.coalesce(func.sum(ReputationEvent.delta), 0).label("score"),
                )
                .join(ReputationEvent, ReputationEvent.user_id == User.id)
                .where(User.is_active.is_(True), User.is_bot.is_(False))
                .group_by(User.id)
                .order_by(func.sum(ReputationEvent.delta).desc(), User.first_name.asc())
                .limit(10)
            )
            rows = list(result.all())

        if not rows:
            await message.answer("🏆 Пока нет участников с изменениями репутации.")
            return

        lines = ["🏆 <b>Топ репутации</b>", ""]
        for index, (user, score) in enumerate(rows, 1):
            name = " ".join(p for p in (user.first_name, user.last_name) if p)
            lines.append(f"{index}. {name} — <b>{int(score)}</b>")
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


@dp.message()
async def community_activity_handler(message: Message) -> None:
    if message.chat.type not in {"group", "supergroup"}:
        return
    if message.from_user is None or message.from_user.is_bot:
        return
    if not os.getenv("DATABASE_URL", "").strip():
        return

    try:
        async for session in get_session():
            user, _ = await sync_telegram_user(session, message.from_user)
            await record_chat_activity(
                session,
                message.chat.id,
                message.chat.title or "Без названия",
                message.chat.type,
                user,
                is_command=bool((message.text or "").lstrip().startswith("/")),
            )
    except Exception as exc:
        print(f"[chat] activity record failed: {exc}", flush=True)


async def setup_bot_commands(bot: Bot) -> None:
    await bot.set_my_commands(
        [
            BotCommand(command="start", description="Открыть меню"),
            BotCommand(command="help", description="Помощь"),
            BotCommand(command="profile", description="Мой профиль"),
            BotCommand(command="rep", description="Моя репутация"),
            BotCommand(command="toprep", description="Топ репутации"),
            BotCommand(command="rules", description="Правила сообщества"),
            BotCommand(command="find", description="Найти участника"),
            BotCommand(command="friends", description="Друзья"),
            BotCommand(command="chatstats", description="Статистика чата"),
            BotCommand(command="mystats", description="Моя активность"),
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
