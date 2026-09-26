from __future__ import annotations

import hashlib
import os
import time

from fastapi import Request
from fastapi.responses import JSONResponse

from app.api.request_id import get_request_id
from sqlalchemy import text

from app.db.engine import configure_engine

WINDOW_SECONDS = 60


def _limit(name: str, default: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer") from exc
    if value <= 0:
        raise RuntimeError(f"{name} must be positive")
    return value


def _client_ip(request: Request) -> str:
    client = request.client
    return client.host if client and client.host else "unknown"


def _bucket_key(request: Request) -> tuple[str, int]:
    init_data = request.headers.get("X-Telegram-Init-Data", "").strip()
    if init_data:
        digest = hashlib.sha256(init_data.encode("utf-8")).hexdigest()
        return f"user:{digest}", _limit("API_RATE_LIMIT_AUTHENTICATED", 120)
    return f"ip:{_client_ip(request)}", _limit("API_RATE_LIMIT_IP", 60)


async def enforce_rate_limit(request: Request) -> None:
    path = request.url.path
    if path.startswith("/health") or path == "/api/v1/health":
        return

    key, limit = _bucket_key(request)
    window = int(time.time() // WINDOW_SECONDS * WINDOW_SECONDS)

    db_engine = configure_engine()
    async with db_engine.begin() as connection:
        result = await connection.execute(
            text(
                """
                INSERT INTO rate_limit_buckets (bucket_key, window_start, request_count)
                VALUES (:bucket_key, to_timestamp(:window_start), 1)
                ON CONFLICT (bucket_key) DO UPDATE
                SET
                    window_start = EXCLUDED.window_start,
                    request_count = CASE
                        WHEN rate_limit_buckets.window_start = EXCLUDED.window_start
                        THEN rate_limit_buckets.request_count + 1
                        ELSE 1
                    END
                RETURNING request_count
                """
            ),
            {"bucket_key": key, "window_start": window},
        )
        count = int(result.scalar_one())

    if count > limit:
        retry_after = WINDOW_SECONDS - (int(time.time()) - window)
        raise RateLimitExceeded(max(1, retry_after))


class RateLimitExceeded(Exception):
    def __init__(self, retry_after: int) -> None:
        self.retry_after = retry_after


class RateLimitMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        from starlette.requests import Request
        request = Request(scope, receive=receive)
        try:
            await enforce_rate_limit(request)
        except RateLimitExceeded as exc:
            request_id = get_request_id() or str(scope.get("state", {}).get("request_id", ""))
            body = {"error": "rate_limit_exceeded", "detail": "Rate limit exceeded", "request_id": request_id, "status_code": 429}
            response = JSONResponse(body, status_code=429, headers={"Retry-After": str(exc.retry_after)})
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)
