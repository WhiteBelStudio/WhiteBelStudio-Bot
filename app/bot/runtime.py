"""Telegram runtime composition and lifecycle."""

from __future__ import annotations

import logging
import os

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from aiogram.types import ErrorEvent

from app.bot.achievements import router as achievements_router
from app.bot.core import router as core_router
from app.bot.economy import router as economy_router
from app.bot.games import router as games_router
from app.bot.middleware import ChatReputationMiddleware

LOGGER = logging.getLogger("bot.runtime")


def build_dispatcher() -> Dispatcher:
    dp = Dispatcher()
    dp.message.middleware(ChatReputationMiddleware())

    @dp.error()
    async def global_error_handler(event: ErrorEvent) -> bool:
        LOGGER.exception("unhandled_update_error", exc_info=event.exception)
        update = event.update
        callback = update.callback_query
        message = update.message or update.edited_message
        if callback is not None:
            try:
                await callback.answer("⚠️ Произошла ошибка. Попробуй ещё раз.", show_alert=True)
            except Exception as exc:
                LOGGER.exception("callback_error_notification_failed", exc_info=exc)
        elif message is not None:
            try:
                await message.answer("⚠️ Произошла ошибка. Попробуй ещё раз.")
            except Exception as exc:
                LOGGER.exception("message_error_notification_failed", exc_info=exc)
        return True

    dp.include_router(core_router)
    dp.include_router(economy_router)
    dp.include_router(achievements_router)
    dp.include_router(games_router)
    return dp


def create_bot() -> Bot:
    token = os.getenv("BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("BOT_TOKEN is not set")

    proxy = os.getenv("TELEGRAM_PROXY", "").strip() or None
    session = AiohttpSession(proxy=proxy)
    bot = Bot(
        token=token,
        session=session,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    LOGGER.info("bot_created", extra={"telegram_proxy": bool(proxy)})
    return bot
