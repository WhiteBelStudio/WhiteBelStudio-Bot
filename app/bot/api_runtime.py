"""FastAPI runtime configuration."""

from __future__ import annotations

import logging
import os

import uvicorn

from app.api.app import app as api_app

LOGGER = logging.getLogger("bot.api_runtime")


async def run_api() -> None:
    host = os.getenv("API_HOST", "0.0.0.0").strip() or "0.0.0.0"
    port = int(os.getenv("API_PORT", "8080"))
    config = uvicorn.Config(
        api_app,
        host=host,
        port=port,
        log_level=os.getenv("LOG_LEVEL", "info").lower(),
        access_log=False,
    )
    LOGGER.info("api_start", extra={"host": host, "port": port})
    await uvicorn.Server(config).serve()
