"""Registro de consola legible y coloreado para el bot."""

from __future__ import annotations

import logging
import sys

from colorama import Fore, Style, just_fix_windows_console

COLORS = {
    logging.DEBUG: Fore.WHITE,
    logging.INFO: Fore.CYAN,
    logging.WARNING: Fore.YELLOW,
    logging.ERROR: Fore.RED,
    logging.CRITICAL: Fore.MAGENTA,
}
CATEGORY_COLORS = {
    "acción": Fore.CYAN,
    "generación": Fore.MAGENTA,
    "entrega": Fore.BLUE,
    "éxito": Fore.GREEN,
    "advertencia": Fore.YELLOW,
    "error": Fore.RED,
}


class ConsoleFormatter(logging.Formatter):
    """Presenta cada evento como un bloque corto fácil de escanear."""

    def format(self, record: logging.LogRecord) -> str:
        timestamp = self.formatTime(record, "%H:%M:%S")
        category = getattr(record, "category", record.levelname)
        color = CATEGORY_COLORS.get(
            category.casefold(), COLORS.get(record.levelno, Fore.WHITE)
        )
        user_id = getattr(record, "user_id", None)
        username = getattr(record, "username", None)
        lines = [
            f"{color}{'─' * 62}",
            f"[{timestamp}] {category.upper()}",
        ]
        if user_id is not None:
            lines.append(f"Usuario : {user_id} ({username or 'sin nombre'})")
        lines.append(f"Acción  : {record.getMessage()}")
        if record.exc_info:
            exception = record.exc_info[1]
            lines.append(f"Detalle : {exception}")
        lines.append(f"{'─' * 62}{Style.RESET_ALL}")
        return "\n".join(lines)


def configure_console_logging(level: int = logging.INFO) -> None:
    just_fix_windows_console()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(ConsoleFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)
    for noisy_logger in ("httpx", "httpcore", "telegram"):
        logging.getLogger(noisy_logger).setLevel(logging.WARNING)


def log_user_action(
    logger: logging.Logger,
    *,
    user_id: int | None,
    username: str | None,
    action: str,
    category: str = "acción",
    level: int = logging.INFO,
    exc_info: bool = False,
) -> None:
    logger.log(
        level,
        action,
        extra={
            "category": category,
            "user_id": user_id,
            "username": username,
        },
        exc_info=exc_info,
    )
