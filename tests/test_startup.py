from __future__ import annotations

import start


def test_production_requires_database_url(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("BOT_TOKEN", "token")
    monkeypatch.delenv("DATABASE_URL", raising=False)

    try:
        start.check_environment()
    except RuntimeError as exc:
        assert "DATABASE_URL" in str(exc)
    else:
        raise AssertionError("production startup must require DATABASE_URL")


def test_non_production_does_not_require_database_url(monkeypatch):
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("BOT_TOKEN", "token")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    start.check_environment()


def test_runtime_directories_are_defined():
    assert {"data", "logs", "backups", ".runtime"} <= set(start.RUNTIME_DIRS)
