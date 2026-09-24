"""WhiteBelStudio Bot entrypoint."""

from __future__ import annotations

import asyncio
import os

from dotenv import load_dotenv

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.types import Message

from app.db.engine import close_db, get_session
from app.db.health import check_database_connection
from app.db.repositories import get_or_create_user

load_dotenv()


dp = Dispatcher()


@dp.message(CommandStart())
async def start_handler(message: Message) -> None:
    database_ok = False
    if os.getenv("DATABASE_URL", "").strip():
        try:
            async for session in get_session():
                await get_or_create_user(
                    session,
                    telegram_id=message.from_user.id,
                    first_name=message.from_user.first_name,
                    username=message.from_user.username,
                    last_name=message.from_user.last_name,
                )
            database_ok = True
        except Exception as exc:
            print(f"[db] user sync failed: {exc}", flush=True)

    suffix = "

🗄 База данных: подключена" if database_ok else ""
    await message.answer(
        "👋 Привет!

"
        "Добро пожаловать в WhiteBelStudio.
"
        "Бот успешно работает! 🚀"
        + suffix
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
        print("[bot] Starting polling...", flush=True)
        await dp.start_polling(bot)
    finally:
        await close_db()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
