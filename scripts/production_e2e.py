from __future__ import annotations

import hashlib
import hmac
import json
import os
import sys
import time
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin, urlparse
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class Probe:
    name: str
    path: str
    expected: tuple[str, ...]


def fail(message: str) -> None:
    print(f"::error::{message}")
    raise SystemExit(1)


def env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        fail(f"{name} is not configured")
    return value


def request_json(base_url: str, path: str, *, headers: dict[str, str] | None = None) -> tuple[int, dict]:
    url = urljoin(base_url.rstrip("/") + "/", path.lstrip("/"))
    request = Request(url, headers={"Accept": "application/json", **(headers or {})})
    try:
        with urlopen(request, timeout=float(os.getenv("E2E_REQUEST_TIMEOUT", "10"))) as response:
            body = response.read().decode("utf-8")
            status = response.status
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        fail(f"{path}: HTTP {exc.code}: {body[:300]}")
    except (URLError, TimeoutError, OSError) as exc:
        fail(f"{path}: connection failed: {exc}")
    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        fail(f"{path}: response is not JSON: {exc}")
    if not isinstance(payload, dict):
        fail(f"{path}: response must be a JSON object")
    return status, payload


def assert_status(name: str, status: int, payload: dict, expected_status: int) -> None:
    if status != expected_status:
        fail(f"{name}: expected HTTP {expected_status}, got {status}")
    if payload.get("status") != "ok":
        fail(f"{name}: expected status=ok")
    print(f"::notice::{name}: PASS")


def build_init_data(bot_token: str, telegram_id: int) -> str:
    now = int(time.time())
    values = {
        "auth_date": str(now),
        "query_id": "production-e2e",
        "user": json.dumps(
            {"id": telegram_id, "first_name": "Production E2E", "is_bot": False},
            separators=(",", ":"),
        ),
    }
    check_string = "\n".join(f"{key}={value}" for key, value in sorted(values.items()))
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    values["hash"] = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()
    return urlencode(values)


def main() -> None:
    base = env("PRODUCTION_HEALTHCHECK_URL").rstrip("/") + "/"
    parsed = urlparse(base)
    if parsed.scheme != "https" and os.getenv("E2E_ALLOW_HTTP", "false").lower() not in {"1", "true", "yes"}:
        fail("PRODUCTION_HEALTHCHECK_URL must use HTTPS")

    probes = (
        Probe("health", "/health", ("status",)),
        Probe("liveness", "/health/live", ("status",)),
        Probe("api-health", "/api/v1/health", ("status", "version")),
        Probe("readiness", "/health/ready", ("status", "database", "revision")),
    )

    for probe in probes:
        status, payload = request_json(base, probe.path)
        assert_status(probe.name, status, payload, 200)
        missing = [key for key in probe.expected if key not in payload]
        if missing:
            fail(f"{probe.name}: missing fields: {', '.join(missing)}")
        if probe.name == "readiness" and payload.get("database") != "ok":
            fail("readiness: database is not ready")
        if probe.name == "readiness" and not str(payload.get("revision", "")).strip():
            fail("readiness: migration revision is empty")

    bot_token = os.getenv("PRODUCTION_E2E_BOT_TOKEN", "").strip()
    telegram_id = os.getenv("PRODUCTION_E2E_TELEGRAM_USER_ID", "").strip()
    if bot_token and telegram_id:
        try:
            user_id = int(telegram_id)
        except ValueError:
            fail("PRODUCTION_E2E_TELEGRAM_USER_ID must be an integer")
        init_data = build_init_data(bot_token, user_id)
        status, payload = request_json(
            base,
            "/api/v1/me",
            headers={"X-Telegram-Init-Data": init_data},
        )
        assert_status("mini-app-auth", status, payload, 200)
        if int(payload.get("telegram_id", -1)) != user_id:
            fail("mini-app-auth: authenticated Telegram ID does not match probe user")
        print("::notice::mini-app-auth: shared Bot/API identity PASS")
    else:
        print("::warning::Mini App authenticated E2E skipped: PRODUCTION_E2E_BOT_TOKEN and PRODUCTION_E2E_TELEGRAM_USER_ID are not both configured")

    print("::notice::Production E2E smoke suite: PASS")


if __name__ == "__main__":
    main()
