from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.request_id import RequestIdMiddleware, get_request_id
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
    return [item.strip() for item in raw.split(",") if item.strip()]


configure_logging()

app = FastAPI(
    title="WhiteBelStudio API",
    version=os.getenv("APP_VERSION", "0.1.0"),
    description="HTTP API for WhiteBelStudio integrations and Mini App.",
    docs_url="/docs"
    if os.getenv("API_DOCS_ENABLED", "true").lower() in {"1", "true", "yes"}
    else None,
    redoc_url="/redoc"
    if os.getenv("API_DOCS_ENABLED", "true").lower() in {"1", "true", "yes"}
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


@app.exception_handler(Exception)
async def unhandled_api_error(request: Request, exc: Exception) -> JSONResponse:
    request_id = get_request_id() or request.headers.get("X-Request-ID") or ""
    logging.getLogger("app.api.errors").exception(
        "unhandled_api_error",
        extra={"request_id": request_id},
    )
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "request_id": request_id,
        },
        headers={"X-Request-ID": request_id},
    )


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
