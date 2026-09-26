from __future__ import annotations

import hashlib
import os
import time

from fastapi import Request
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
        from fastapi import HTTPException

        retry_after = WINDOW_SECONDS - (int(time.time()) - window)
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded",
            headers={"Retry-After": str(max(1, retry_after))},
        )
