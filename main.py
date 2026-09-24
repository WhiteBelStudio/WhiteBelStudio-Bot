"""WhiteBelStudio Bot entrypoint."""

from __future__ import annotations

import asyncio
import os

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode


async def main() -> None:
    token = os.environ["BOT_TOKEN"]
    proxy = os.getenv("TELEGRAM_PROXY", "").strip() or None

    session = AiohttpSession(proxy=proxy)
    bot = Bot(
        token=token,
        session=session,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()

    if proxy:
        print("[bot] Telegram proxy: enabled", flush=True)
    else:
        print("[bot] Telegram proxy: disabled", flush=True)

    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
