#!/usr/bin/env python3
"""Pterodactyl bootstrap: sync GitHub, then run the current application."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = os.getenv("GITHUB_REPOSITORY", "WhiteBelStudio/WhiteBelStudio-Bot")
BRANCH = os.getenv("GITHUB_BRANCH", "main")
APP_DIR = ROOT / ".runtime" / "app"


def run(*args: str, cwd: Path | None = None) -> None:
    subprocess.run(args, cwd=cwd or ROOT, check=True)


def sync_repo() -> None:
    APP_DIR.parent.mkdir(parents=True, exist_ok=True)
    if not (APP_DIR / ".git").exists():
        if APP_DIR.exists():
            shutil.rmtree(APP_DIR)
        print(f"[deploy] Cloning {REPO}@{BRANCH}", flush=True)
        run("git", "clone", "--depth", "1", "--branch", BRANCH,
            f"https://github.com/{REPO}.git", str(APP_DIR))
        return
    print(f"[deploy] Updating {REPO}@{BRANCH}", flush=True)
    run("git", "fetch", "--depth", "1", "origin", BRANCH, cwd=APP_DIR)
    run("git", "reset", "--hard", f"origin/{BRANCH}", cwd=APP_DIR)


def install_dependencies() -> None:
    requirements = APP_DIR / "requirements.txt"
    if requirements.exists():
        print("[deploy] Installing requirements", flush=True)
        run(sys.executable, "-m", "pip", "install", "-r", str(requirements))


def start_application() -> None:
    app_main = APP_DIR / "main.py"
    if not app_main.exists():
        raise RuntimeError("GitHub repository does not contain main.py")
    print("[deploy] Starting current GitHub version", flush=True)
    os.execv(sys.executable, [sys.executable, str(app_main)])


def main() -> None:
    sync_repo()
    install_dependencies()
    start_application()


if __name__ == "__main__":
    main()
