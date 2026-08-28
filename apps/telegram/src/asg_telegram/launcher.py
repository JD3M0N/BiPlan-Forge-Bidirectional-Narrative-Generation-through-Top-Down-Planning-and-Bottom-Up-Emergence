"""Launch the bot in a separate Windows console."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys


def launch_command() -> list[str]:
    """Launch command."""
    return [sys.executable, "-m", "asg_telegram.app"]


def parser() -> argparse.ArgumentParser:
    """Build the detached Telegram launcher command-line parser."""
    return argparse.ArgumentParser(description="Abre ASG Telegram en una consola independiente")


def main(argv: list[str] | None = None) -> int:
    """Run the command-line entry point."""
    parser().parse_args(argv)
    command = launch_command()
    if os.name != "nt":
        from .app import main as run_bot

        return run_bot([])
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
