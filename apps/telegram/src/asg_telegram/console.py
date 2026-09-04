"""Readable, colored console logging for the Telegram bot."""

from __future__ import annotations

import logging
import re
import sys

from asg_top_down.errors import ASGError
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


def _redact_diagnostic(value: str) -> str:
    """Handle the redact diagnostic operation for component."""
    value = re.sub(r"AIza[0-9A-Za-z_-]{20,}", "[REDACTED]", value)
    value = re.sub(
        r"(?i)((?:api[_ -]?key|token|authorization)\s*[:=]\s*)\S+",
        r"\1[REDACTED]",
        value,
    )
    value = re.sub(r"\d+:[A-Za-z0-9_-]{35}", "[REDACTED]", value)
    return value


class ConsoleFormatter(logging.Formatter):
    """Render each log record as a short, readable block."""

    def format(self, record: logging.LogRecord) -> str:
        """Format one record for display."""
        timestamp = self.formatTime(record, "%H:%M:%S")
        category = getattr(record, "category", record.levelname)
        color = CATEGORY_COLORS.get(category.casefold(), COLORS.get(record.levelno, Fore.WHITE))
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
            if isinstance(exception, ASGError):
                detail = exception.public_message()
                lines.append(f"Etapa   : {exception.stage}")
            else:
                message = _redact_diagnostic(str(exception).strip()) or "sin mensaje"
                detail = f"Error interno inesperado ({type(exception).__name__}): {message}"
            lines.append(f"Detalle : {detail}")
            if not isinstance(exception, ASGError):
                trace = _redact_diagnostic(self.formatException(record.exc_info))
                lines.append(f"Traza   : {trace}")
        lines.append(f"{'─' * 62}{Style.RESET_ALL}")
        return "\n".join(lines)


def configure_console_logging(level: int = logging.INFO) -> None:
    """Configure console logging."""
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
    """Handle the log user action operation for component."""
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
