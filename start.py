"""Production bootstrap and safe GitHub updater for Pterodactyl."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REPO = os.getenv("GITHUB_REPOSITORY", "WhiteBelStudio/WhiteBelStudio-Bot")
BRANCH = os.getenv("GITHUB_BRANCH", "main")
UPDATE_ENABLED = os.getenv("GITHUB_UPDATE_ENABLED", "true").lower() in {"1", "true", "yes"}
REQUIREMENTS = ROOT / "requirements.txt"


def log(message: str) -> None:
    print(f"[start] {message}", flush=True)


def run(command: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    safe = " ".join("<token>" if "@" in part and "://" in part else part for part in command)
    log("$ " + safe)
    return subprocess.run(
        command,
        cwd=ROOT,
        check=check,
        text=True,
        capture_output=False,
    )


def git(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return run(["git", *args], check=check)


def check_environment() -> None:
    missing = [name for name in ("BOT_TOKEN",) if not os.getenv(name)]
    if missing:
        raise RuntimeError("Missing required environment variables: " + ", ".join(missing))


def ensure_runtime_dirs() -> None:
    for name in ("data", "logs", "backups"):
        (ROOT / name).mkdir(exist_ok=True)


def update_from_github() -> str | None:
    """Update a git checkout while preserving ignored runtime data and .env."""
    if not UPDATE_ENABLED:
        log("GitHub updater disabled")
        return None

    if not (ROOT / ".git").exists():
        log("No .git directory; assuming Pterodactyl already contains the release")
        return None

    log(f"Checking GitHub: {REPO}@{BRANCH}")
    git("remote", "set-url", "origin", f"https://github.com/{REPO}.git")
    git("fetch", "--prune", "origin", BRANCH)

    current = git("rev-parse", "HEAD").stdout.strip()
    remote = git("rev-parse", f"origin/{BRANCH}").stdout.strip()

    if current == remote:
        log(f"Already up to date: {current[:12]}")
        return current

    log(f"Updating {current[:12]} -> {remote[:12]}")

    # Do not run git clean/reset with flags that remove untracked runtime data.
    # .env, data/, logs/ and backups/ are ignored by the repository.
    git("reset", "--hard", f"origin/{BRANCH}")

    updated = git("rev-parse", "HEAD").stdout.strip()
    log(f"Updated to {updated[:12]}")
    return updated


def install_dependencies() -> None:
    if REQUIREMENTS.exists():
        run([sys.executable, "-m", "pip", "install", "-r", str(REQUIREMENTS)])


def run_migrations() -> None:
    if (ROOT / "alembic.ini").exists() and (ROOT / "migrations").exists():
        log("Running database migrations")
        result = run([sys.executable, "-m", "alembic", "upgrade", "head"], check=False)
        if result.returncode != 0:
            raise RuntimeError("Database migration failed")


def health_check() -> None:
    main_file = ROOT / "main.py"
    if not main_file.exists():
        raise RuntimeError("main.py is missing after update")

    result = run(
        [sys.executable, "-m", "compileall", "-q", str(ROOT / "app"), str(main_file)],
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError("Python compile check failed")

    log("Health check: OK")


def start_bot() -> None:
    main_file = ROOT / "main.py"
    run([sys.executable, str(main_file)])


def main() -> None:
    log("WhiteBelStudio Bot production bootstrap")
    log(f"Python: {sys.version.split()[0]}")
    log(f"Root: {ROOT}")

    ensure_runtime_dirs()
    check_environment()

    previous_commit = None
    try:
        previous_commit = git("rev-parse", "HEAD", check=False).stdout.strip() or None
        update_from_github()
        install_dependencies()
        run_migrations()
        health_check()
    except Exception as exc:
        log(f"Bootstrap failed: {exc}")
        if previous_commit and (ROOT / ".git").exists():
            log(f"Rolling back code to {previous_commit[:12]}")
            git("reset", "--hard", previous_commit, check=False)
        raise

    start_bot()


if __name__ == "__main__":
    main()
