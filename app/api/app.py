from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.db.health import check_database_connection, check_database_schema


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield


def _cors_origins() -> list[str]:
    raw = os.getenv("API_CORS_ORIGINS", "").strip()
    if not raw:
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


app = FastAPI(
    title="WhiteBelStudio API",
    version=os.getenv("APP_VERSION", "0.1.0"),
    description="HTTP API for WhiteBelStudio integrations and Mini App.",
    docs_url="/docs" if os.getenv("API_DOCS_ENABLED", "true").lower() in {"1", "true", "yes"} else None,
    redoc_url="/redoc" if os.getenv("API_DOCS_ENABLED", "true").lower() in {"1", "true", "yes"} else None,
)

origins = _cors_origins()
if origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Telegram-Init-Data"],
    )


@app.exception_handler(Exception)
async def unhandled_api_error(_: Request, exc: Exception) -> JSONResponse:
    print(f"[api] unhandled error: {exc!r}", flush=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/live", tags=["health"])
async def liveness() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/ready", tags=["health"])
async def readiness() -> dict[str, str]:
    await check_database_connection()
    revision = await check_database_schema()
    return {"status": "ok", "database": "ok", "revision": revision}


@app.get("/api/v1/health", tags=["health"])
async def api_health() -> dict[str, str]:
    return {"status": "ok", "version": app.version}
