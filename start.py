"""Production bootstrap for Pterodactyl.

The updater is intentionally conservative:
- secrets and runtime data are never overwritten;
- GitHub is the source of application code;
- dependencies are installed after an update;
- the actual bot is started only after bootstrap checks pass.

A full transactional rollback will be added together with the release/update
manager. This first production bootstrap keeps the server state safe.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REQUIREMENTS = ROOT / "requirements.txt"


def log(message: str) -> None:
    print(f"[start] {message}", flush=True)


def run(command: list[str]) -> None:
    log("$ " + " ".join(command))
    subprocess.run(command, cwd=ROOT, check=True)


def check_environment() -> None:
    required = ["BOT_TOKEN"]
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        raise RuntimeError(
            "Missing required environment variables: " + ", ".join(missing)
        )


def install_dependencies() -> None:
    if REQUIREMENTS.exists():
        run([sys.executable, "-m", "pip", "install", "-r", str(REQUIREMENTS)])


def main() -> None:
    log("WhiteBelStudio Bot bootstrap")
    log(f"Python: {sys.version.split()[0]}")
    log(f"Root: {ROOT}")

    (ROOT / "data").mkdir(exist_ok=True)
    (ROOT / "logs").mkdir(exist_ok=True)
    (ROOT / "backups").mkdir(exist_ok=True)

    check_environment()
    install_dependencies()

    main_file = ROOT / "main.py"
    if not main_file.exists():
        raise RuntimeError("main.py is not present yet")

    run([sys.executable, str(main_file)])


if __name__ == "__main__":
    main()
