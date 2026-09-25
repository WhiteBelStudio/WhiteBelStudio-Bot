from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.errors import (
    http_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from app.api.request_id import RequestIdMiddleware
from app.api.request_logging import RequestLoggingMiddleware
from app.api.routes import router as api_router
from app.logging import configure_logging
from app.services.health import check_readiness


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield


def _cors_origins() -> list[str]:
    raw = os.getenv("API_CORS_ORIGINS", "").strip()
    if not raw:
        return []
    origins = [item.strip() for item in raw.split(",") if item.strip()]
    if "*" in origins:
        raise RuntimeError("API_CORS_ORIGINS must not contain '*'")
    return origins


configure_logging()

app = FastAPI(
    title="WhiteBelStudio API",
    version=os.getenv("APP_VERSION", "0.1.0"),
    description="HTTP API for WhiteBelStudio integrations and Mini App.",
    docs_url="/docs"
    if os.getenv("API_DOCS_ENABLED", "false").lower() in {"1", "true", "yes"}
    else None,
    redoc_url="/redoc"
    if os.getenv("API_DOCS_ENABLED", "false").lower() in {"1", "true", "yes"}
    else None,
)

# RequestId must be the outer middleware so the correlation ID remains available
# while RequestLoggingMiddleware emits its final access event.
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(RequestIdMiddleware)

origins = _cors_origins()
if origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "X-Telegram-Init-Data",
            "X-Request-ID",
        ],
        expose_headers=["X-Request-ID"],
    )


app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/live", tags=["health"])
async def liveness() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/ready", tags=["health"])
async def readiness() -> dict[str, str]:
    revision = await check_readiness()
    return {"status": "ok", "database": "ok", "revision": revision}


@app.get("/api/v1/health", tags=["health"])
async def api_health() -> dict[str, str]:
    return {"status": "ok", "version": app.version}


app.include_router(api_router)
