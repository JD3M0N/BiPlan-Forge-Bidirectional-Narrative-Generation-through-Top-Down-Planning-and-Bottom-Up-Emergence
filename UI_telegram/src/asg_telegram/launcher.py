"""Lanza el bot en una consola independiente en Windows."""

from __future__ import annotations

import os
import subprocess
import sys


def launch_command() -> list[str]:
    return [sys.executable, "-m", "asg_telegram.app"]


def main() -> int:
    command = launch_command()
    if os.name != "nt":
        from .app import main as run_bot

        return run_bot()
    try:
        subprocess.Popen(
            command,
            creationflags=subprocess.CREATE_NEW_CONSOLE,
            close_fds=True,
        )
    except OSError as exc:
        print(f"No se pudo abrir la consola del bot: {exc}", file=sys.stderr)
        return 1
    print("Bot iniciado en una consola independiente.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
