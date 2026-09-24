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
RUNTIME_DIRS = ("data", "logs", "backups", ".runtime")


def log(message: str) -> None:
    print(f"[start] {message}", flush=True)


def run(command: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    log("$ " + " ".join(command))
    return subprocess.run(command, cwd=ROOT, check=check, text=True)


def git(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return run(["git", *args], check=check)


def check_environment() -> None:
    required = ("BOT_TOKEN",)
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        raise RuntimeError("Missing required environment variables: " + ", ".join(missing))


def ensure_runtime_dirs() -> None:
    for name in RUNTIME_DIRS:
        (ROOT / name).mkdir(exist_ok=True)


def ensure_git_checkout() -> None:
    if not (ROOT / ".git").exists():
        raise RuntimeError(
            "Pterodactyl project is not a Git checkout. Clone "
            f"https://github.com/{REPO}.git into the server project directory first."
        )


def update_from_github() -> tuple[str, str]:
    """Update a Git checkout while preserving ignored runtime data and .env."""
    ensure_git_checkout()

    if not UPDATE_ENABLED:
        current = git("rev-parse", "HEAD").stdout.strip()
        log("GitHub updater disabled")
        return current, current

    log(f"Checking GitHub: {REPO}@{BRANCH}")
    git("remote", "set-url", "origin", f"https://github.com/{REPO}.git")
    git("fetch", "--prune", "origin", BRANCH)

    current = git("rev-parse", "HEAD").stdout.strip()
    remote = git("rev-parse", f"origin/{BRANCH}").stdout.strip()

    if current == remote:
        log(f"Already up to date: {current[:12]}")
        return current, remote

    log(f"Updating {current[:12]} -> {remote[:12]}")
    git("reset", "--hard", f"origin/{BRANCH}")
    updated = git("rev-parse", "HEAD").stdout.strip()
    log(f"Updated to {updated[:12]}")
    return current, updated


def install_dependencies() -> None:
    if not REQUIREMENTS.exists():
        raise RuntimeError("requirements.txt is missing")

    run([sys.executable, "-m", "pip", "install", "-r", str(REQUIREMENTS)])


def run_migrations() -> None:
    migration_env = ROOT / "migrations" / "env.py"
    if not migration_env.exists():
        log("Alembic environment is not configured yet; migrations skipped")
        return

    log("Running database migrations")
    result = run([sys.executable, "-m", "alembic", "upgrade", "head"], check=False)
    if result.returncode != 0:
        raise RuntimeError("Database migration failed")


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

    log("Health check: OK")


def rollback_code(previous_commit: str) -> None:
    if not previous_commit or not (ROOT / ".git").exists():
        return

    log(f"Rolling back code to {previous_commit[:12]}")
    git("reset", "--hard", previous_commit, check=False)

    # Restore the dependency set belonging to the previous code revision.
    previous_requirements = ROOT / "requirements.txt"
    if previous_requirements.exists():
        run(
            [sys.executable, "-m", "pip", "install", "-r", str(previous_requirements)],
            check=False,
        )


def start_bot() -> None:
    run([sys.executable, str(ROOT / "main.py")])


def main() -> None:
    log("WhiteBelStudio Bot production bootstrap")
    log(f"Python: {sys.version.split()[0]}")
    log(f"Root: {ROOT}")
    log(f"Repository: {REPO}@{BRANCH}")

    ensure_runtime_dirs()
    check_environment()

    previous_commit = ""
    updated_commit = ""

    try:
        previous_commit, updated_commit = update_from_github()
        install_dependencies()
        health_check()
        run_migrations()
        health_check()
        log(f"Bootstrap ready at {updated_commit[:12]}")
    except Exception as exc:
        log(f"Bootstrap failed: {exc}")
        if previous_commit and updated_commit and previous_commit != updated_commit:
            rollback_code(previous_commit)
        raise

    start_bot()


if __name__ == "__main__":
    main()
