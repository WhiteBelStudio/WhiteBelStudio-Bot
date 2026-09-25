from __future__ import annotations

import logging
import time
from typing import Any

from app.api.request_id import get_request_id

logger = logging.getLogger("app.api.access")


class RequestLoggingMiddleware:
    """Log one structured access event for every HTTP request."""

    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        started = time.perf_counter()
        status_code = 500

        async def send_with_status(message: dict) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = int(message["status"])
            await send(message)

        try:
            await self.app(scope, receive, send_with_status)
        finally:
            duration_ms = round((time.perf_counter() - started) * 1000, 2)
            client = scope.get("client")
            logger.info(
                "http_request",
                extra={
                    "request_id": get_request_id(),
                    "method": scope.get("method"),
                    "path": scope.get("path"),
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                    "client_ip": client[0] if client else None,
                },
            )
