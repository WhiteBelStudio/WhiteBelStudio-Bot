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
from aiogram.types import Message

from app.db.engine import close_db, get_session
from app.db.health import check_database_connection
from app.services.communication import format_message, get_messages, send_message
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

    await message.answer(
        "👋 Привет!\n\n"
        "Добро пожаловать в WhiteBelStudio.\n"
        f"{account_status}\n\n"
        "👤 /profile — профиль\n"
        "🔎 /find — найти людей\n"
        "👥 /friends — друзья\n"
        "📨 /requests — заявки\n"
        "💬 /msg @username текст — сообщение\n"
        "📖 /chat @username — история"
        + suffix
    )


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


@dp.message(Command("msg"))
async def message_handler(message: Message) -> None:
    if message.from_user is None:
        return

    parts = (message.text or "").split(maxsplit=2)
    if len(parts) < 3:
        await message.answer("Использование: <code>/msg @username текст</code>")
        return

    username, body = parts[1], parts[2]

    try:
        async for session in get_session():
            sender, _ = await sync_telegram_user(session, message.from_user)
            target = await get_user_by_username(session, username)

            if target is None:
                result, record = "not_found", None
            else:
                result, record = await send_message(session, sender.id, target.id, body)

        responses = {
            "not_found": "❌ Пользователь не найден.",
            "self": "🙂 Нельзя написать самому себе.",
            "empty": "❌ Сообщение пустое.",
            "too_long": "❌ Сообщение слишком длинное (максимум 4000 символов).",
            "unavailable": "❌ Пользователь недоступен.",
            "not_friends": "🔒 Сначала добавь пользователя в друзья.",
        }

        if result != "sent":
            await message.answer(responses.get(result, "⚠️ Не удалось отправить сообщение."))
            return

        assert target is not None and record is not None
        await message.bot.send_message(
            target.telegram_id,
            "💬 <b>Новое сообщение</b>\n\n"
            f"{body}\n\n"
            f"Ответить: <code>/msg @{message.from_user.username or 'username'} текст</code>",
        )
        await message.answer("✅ Сообщение отправлено.")

    except Exception as exc:
        print(f"[communication] send failed: {exc}", flush=True)
        await message.answer("⚠️ Не удалось отправить сообщение.")


@dp.message(Command("chat"))
async def chat_handler(message: Message) -> None:
    if message.from_user is None:
        return

    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Использование: <code>/chat @username</code>")
        return

    try:
        async for session in get_session():
            current, _ = await sync_telegram_user(session, message.from_user)
            target = await get_user_by_username(session, parts[1].strip().split()[0])
            if target is None:
                messages = []
            else:
                messages = await get_messages(session, current.id, target.id)

        if target is None:
            await message.answer("❌ Пользователь не найден.")
            return

        if not messages:
            await message.answer("💬 История сообщений пока пустая.")
            return

        lines = ["💬 <b>Последние сообщения</b>", ""]
        for item in messages:
            lines.append(format_message(item, current.id))
        await message.answer("\n".join(lines))

    except Exception as exc:
        print(f"[communication] history failed: {exc}", flush=True)
        await message.answer("⚠️ Не удалось загрузить историю.")


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
        print("[bot] Starting polling...", flush=True)
        await dp.start_polling(bot)
    finally:
        await close_db()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
