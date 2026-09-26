from __future__ import annotations

import contextvars
import logging
import uuid
from collections.abc import Awaitable, Callable

from starlette.types import ASGIApp, Message, Receive, Scope, Send

REQUEST_ID_HEADER = "X-Request-ID"
_request_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "request_id", default=None
)


def get_request_id() -> str | None:
    return _request_id.get()


def _incoming_request_id(scope: Scope) -> str | None:
    for key, value in scope.get("headers", []):
        if key.lower() == b"x-request-id":
            try:
                candidate = value.decode("ascii").strip()
            except UnicodeDecodeError:
                return None
            if len(candidate) <= 128:
                try:
                    parsed = uuid.UUID(candidate)
                except ValueError:
                    return None
                if str(parsed) == candidate.lower():
                    return str(parsed)
            return None
    return None


class RequestIdMiddleware:
    """Attach a stable correlation ID to every HTTP request and response."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = _incoming_request_id(scope) or str(uuid.uuid4())
        scope.setdefault("state", {})["request_id"] = request_id
        token = _request_id.set(request_id)
        logger = logging.getLogger("app.api")

        async def send_with_request_id(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers = [
                    (key, value)
                    for key, value in headers
                    if key.lower() != REQUEST_ID_HEADER.lower().encode("ascii")
                ]
                headers.append(
                    (REQUEST_ID_HEADER.lower().encode("ascii"), request_id.encode("ascii"))
                )
                message = {**message, "headers": headers}
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        except Exception:
            logger.exception("Unhandled HTTP request error request_id=%s", request_id)
            raise
        finally:
            _request_id.reset(token)
