"""Launch the bot in a separate, professional-looking console window."""

from __future__ import annotations

import argparse
import logging
import os
import subprocess
import sys
import traceback

from .terminal import disable_quick_edit, set_console_title, wait_for_enter

LOGGER = logging.getLogger(__name__)


def launch_command() -> list[str]:
    """Return the command that opens the hosted bot in its own window."""
    return [sys.executable, "-m", "asg_telegram.launcher", "--hosted"]


def parser() -> argparse.ArgumentParser:
    """Build the detached Telegram launcher command-line parser."""
    parsed = argparse.ArgumentParser(description="Abre ASG Telegram en una consola independiente")
    parsed.add_argument(
        "--hosted",
        action="store_true",
        help="Ejecuta el bot en esta consola, en vez de abrir una nueva.",
    )
    return parsed


def run_hosted(*, run_bot=None, input_fn=input) -> int:
    """Run the bot in the current console, keeping the window open on failure.

    Importing the application here, instead of at module load time, means a
    broken install still shows its error before the window closes: the parent
    process that opens this console pays no cost for that import at all.
    """
    if run_bot is None:
        from .app import main as run_bot
    restore_quick_edit = disable_quick_edit()
    try:
        set_console_title("ASG Telegram")
        code = run_bot([])
    except KeyboardInterrupt:
        print("\nBot detenido.")
        restore_quick_edit()
        return 0
    except Exception:
        traceback.print_exc()
        code = 1
    restore_quick_edit()
    if code != 0:
        wait_for_enter("\nPresiona Enter para cerrar esta ventana... ", input_fn)
    return code


def main(argv: list[str] | None = None) -> int:
    """Run the command-line entry point."""
    args = parser().parse_args(argv)
    if args.hosted:
        return run_hosted()
    command = launch_command()
    if os.name != "nt":
        return run_hosted()
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
