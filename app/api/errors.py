from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.request_id import get_request_id

LOGGER = logging.getLogger("app.api.errors")


def _request_id(request: Request) -> str:
    return (
        get_request_id()
        or request.headers.get("X-Request-ID")
        or str(getattr(request.state, "request_id", "") or "")
    )


def _safe_detail(detail: Any, *, fallback: str) -> str:
    if isinstance(detail, str) and detail.strip():
        return detail
    if isinstance(detail, Mapping) and isinstance(detail.get("message"), str):
        return str(detail["message"])
    return fallback


def _response(
    *,
    status_code: int,
    error: str,
    detail: str,
    request_id: str,
    extra: dict[str, Any] | None = None,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    content: dict[str, Any] = {
        "error": error,
        "detail": detail,
        "request_id": request_id,
        "status_code": status_code,
    }
    if extra:
        content.update(extra)
    response_headers = dict(headers or {})
    if request_id:
        response_headers["X-Request-ID"] = request_id
    return JSONResponse(status_code=status_code, content=content, headers=response_headers)


async def http_exception_handler(
    request: Request,
    exc: StarletteHTTPException,
) -> JSONResponse:
    request_id = _request_id(request)
    detail = _safe_detail(exc.detail, fallback="HTTP request failed")
    return _response(
        status_code=exc.status_code,
        error="http_error",
        detail=detail,
        request_id=request_id,
        headers=exc.headers,
    )


async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    request_id = _request_id(request)
    errors = [
        {
            "loc": list(error.get("loc", ())),
            "msg": str(error.get("msg", "Invalid value")),
            "type": str(error.get("type", "validation_error")),
        }
        for error in exc.errors()
    ]
    return _response(
        status_code=422,
        error="validation_error",
        detail="Request validation failed",
        request_id=request_id,
        extra={"errors": errors},
    )


async def unhandled_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    request_id = _request_id(request)
    LOGGER.exception(
        "unhandled_api_error",
        extra={"request_id": request_id},
        exc_info=exc,
    )
    return _response(
        status_code=500,
        error="internal_error",
        detail="Internal server error",
        request_id=request_id,
    )
