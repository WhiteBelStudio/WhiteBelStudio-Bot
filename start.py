"""Production bootstrap and safe GitHub updater for Pterodactyl."""

from __future__ import annotations

import asyncio
import logging
import os
import subprocess
import sys
import time
from pathlib import Path

from app.db.engine import close_db
from app.db.health import check_database_connection, check_database_schema
from app.logging import configure_logging


ROOT = Path(__file__).resolve().parent
REPO = os.getenv("GITHUB_REPOSITORY", "WhiteBelStudio/WhiteBelStudio-Bot")
BRANCH = os.getenv("GITHUB_BRANCH", "main")
UPDATE_ENABLED = os.getenv("GITHUB_UPDATE_ENABLED", "true").lower() in {"1", "true", "yes"}
REQUIREMENTS = ROOT / "requirements.txt"
RUNTIME_DIRS = ("data", "logs", "backups", ".runtime")
LOGGER = logging.getLogger("bootstrap")


def run(command: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    LOGGER.info("command", extra={"command": " ".join(command)})
    return subprocess.run(command, cwd=ROOT, check=check, text=True)


def git(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return run(["git", *args], check=check)


def check_environment() -> None:
    required = ["BOT_TOKEN"]
    if os.getenv("APP_ENV", "production").lower() == "production":
        required.append("DATABASE_URL")
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        raise RuntimeError("Missing required environment variables: " + ", ".join(missing))


def ensure_runtime_dirs() -> None:
    for name in RUNTIME_DIRS:
        (ROOT / name).mkdir(parents=True, exist_ok=True)


def ensure_git_checkout() -> None:
    if not (ROOT / ".git").exists():
        raise RuntimeError(
            "Pterodactyl project is not a Git checkout. Clone "
            f"https://github.com/{REPO}.git into the server project directory first."
        )


def update_from_github() -> tuple[str, str]:
    """Fast-forward the deployment checkout to the configured remote branch."""
    ensure_git_checkout()

    current = git("rev-parse", "HEAD").stdout.strip()
    if not UPDATE_ENABLED:
        LOGGER.info("github_updater_disabled", extra={"commit": current})
        return current, current

    LOGGER.info("github_update_check", extra={"repository": REPO, "branch": BRANCH})
    git("remote", "set-url", "origin", f"https://github.com/{REPO}.git")
    git("fetch", "--prune", "origin", BRANCH)
    remote = git("rev-parse", f"origin/{BRANCH}").stdout.strip()

    if current == remote:
        LOGGER.info("github_already_current", extra={"commit": current})
        return current, remote

    LOGGER.info(
        "github_update",
        extra={"previous_commit": current, "updated_commit": remote},
    )
    git("reset", "--hard", f"origin/{BRANCH}")
    updated = git("rev-parse", "HEAD").stdout.strip()
    return current, updated


def install_dependencies() -> None:
    if not REQUIREMENTS.exists():
        raise RuntimeError("requirements.txt is missing")
    run([sys.executable, "-m", "pip", "install", "-r", str(REQUIREMENTS)])


def run_migrations() -> None:
    migration_env = ROOT / "migrations" / "env.py"
    if not migration_env.exists():
        raise RuntimeError("Alembic environment is missing; refusing production startup")

    LOGGER.info("database_migration_start")
    result = run([sys.executable, "-m", "alembic", "upgrade", "head"], check=False)
    if result.returncode != 0:
        raise RuntimeError("Database migration failed")
    LOGGER.info("database_migration_complete")


def wait_for_database() -> None:
    attempts = max(1, int(os.getenv("DB_STARTUP_RETRIES", "10")))
    delay = max(0.1, float(os.getenv("DB_STARTUP_RETRY_DELAY", "2")))

    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            asyncio.run(check_database_connection())
            LOGGER.info("database_connection_ready", extra={"attempt": attempt})
            return
        except Exception as exc:
            last_error = exc
            LOGGER.warning(
                "database_not_ready",
                extra={"attempt": attempt, "max_attempts": attempts, "error": str(exc)},
            )
            if attempt < attempts:
                time.sleep(delay)

    raise RuntimeError(f"Database unavailable after {attempts} attempts") from last_error


def health_check() -> None:
    main_file = ROOT / "main.py"
    if not main_file.exists():
        raise RuntimeError("main.py is missing after update")

    targets = [str(main_file)]
    app_dir = ROOT / "app"
    if app_dir.exists():
        targets.append(str(app_dir))

    result = run([sys.executable, "-m", "compileall", "-q", *targets], check=False)
    if result.returncode != 0:
        raise RuntimeError("Python compile check failed")

    LOGGER.info("python_compile_check_ok")


def rollback_code(previous_commit: str) -> None:
    if not previous_commit or not (ROOT / ".git").exists():
        return

    LOGGER.warning("code_rollback", extra={"commit": previous_commit})
    git("reset", "--hard", previous_commit, check=False)

    if REQUIREMENTS.exists():
        run(
            [sys.executable, "-m", "pip", "install", "-r", str(REQUIREMENTS)],
            check=False,
        )


def start_bot() -> None:
    LOGGER.info("bot_process_start")
    run([sys.executable, str(ROOT / "main.py")])


def main() -> None:
    configure_logging()
    LOGGER.info(
        "bootstrap_start",
        extra={
            "python": sys.version.split()[0],
            "repository": REPO,
            "branch": BRANCH,
            "root": str(ROOT),
        },
    )

    ensure_runtime_dirs()
    check_environment()

    previous_commit = ""
    updated_commit = ""
    migration_started = False

    try:
        previous_commit, updated_commit = update_from_github()
        install_dependencies()
        health_check()

        # Production migrations are mandatory. Never start against an unknown schema.
        wait_for_database()
        migration_started = True
        run_migrations()
        health_check()

        revision = asyncio.run(check_database_schema())
        LOGGER.info(
            "database_schema_ok",
            extra={"revision": revision, "commit": updated_commit},
        )
        LOGGER.info("bootstrap_ready", extra={"commit": updated_commit})
    except Exception:
        LOGGER.exception("bootstrap_failed")
        if not migration_started and previous_commit and updated_commit and previous_commit != updated_commit:
            rollback_code(previous_commit)
        elif migration_started:
            LOGGER.error("code_rollback_skipped_after_migration")
        raise
    finally:
        # close_db is harmless before the main process starts and releases failed-start resources.
        try:
            asyncio.run(close_db())
        except Exception:
            LOGGER.exception("database_close_failed")

    start_bot()


if __name__ == "__main__":
    main()
