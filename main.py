"""WhiteBelStudio Bot production composition root."""

from __future__ import annotations

import asyncio
import logging
import os

from dotenv import load_dotenv

from app.bot.api_runtime import run_api
from app.bot.core import setup_bot_commands
from app.bot.runtime import build_dispatcher, create_bot
from app.db.engine import close_db
from app.db.health import check_database_connection
from app.logging import configure_logging

load_dotenv()

LOGGER = logging.getLogger("bot.main")

dp = build_dispatcher()


async def main() -> None:
    configure_logging()
    bot = create_bot()

    if os.getenv("DATABASE_URL", "").strip():
        try:
            await check_database_connection()
            LOGGER.info("database_connection_ok")
        except Exception as exc:
            LOGGER.exception("database_connection_unavailable", exc_info=exc)
    else:
        LOGGER.warning("database_url_not_configured")

    try:
        await setup_bot_commands(bot)
        LOGGER.info("bot_commands_configured")
        LOGGER.info("bot_polling_start")
        await asyncio.gather(
            dp.start_polling(bot),
            run_api(),
        )
    finally:
        await close_db()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
