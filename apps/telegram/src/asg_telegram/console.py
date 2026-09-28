"""Readable, colored console logging for the Telegram bot's hosted window."""

from __future__ import annotations

import logging
import re
import sys

from asg_core import use_utf8_output
from colorama import Fore, Style, just_fix_windows_console

from .contract import GenerationFailure

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
    "progreso": Fore.BLUE,
    "entrega": Fore.BLUE,
    "éxito": Fore.GREEN,
    "advertencia": Fore.YELLOW,
    "error": Fore.RED,
    "sistema": Fore.WHITE,
}
_LEVEL_CATEGORY = {
    logging.DEBUG: "sistema",
    logging.WARNING: "advertencia",
    logging.ERROR: "error",
    logging.CRITICAL: "error",
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
    """Render each log record as one compact, colored line, plus detail on failure."""

    def format(self, record: logging.LogRecord) -> str:
        """Format one record for display."""
        timestamp = self.formatTime(record, "%H:%M:%S")
        category = getattr(record, "category", None) or _LEVEL_CATEGORY.get(
            record.levelno, "acción"
        )
        color = CATEGORY_COLORS.get(category.casefold(), COLORS.get(record.levelno, Fore.WHITE))
        user_id = getattr(record, "user_id", None)
        username = getattr(record, "username", None)
        job_id = getattr(record, "job_id", None)
        who = f"{username or 'sin nombre'} ({user_id})" if user_id is not None else "sistema"
        if job_id:
            who += f" · {job_id[:8]}"
        line = f"{color}{timestamp}  {category.upper():<12}{who:<28}{record.getMessage()}"
        lines = [line]
        if record.exc_info:
            exception = record.exc_info[1]
            if isinstance(exception, GenerationFailure):
                lines.append(f"    Código  : {exception.code}")
                lines.append(f"    Etapa   : {exception.stage}")
                detail = exception.summary
            else:
                message = _redact_diagnostic(str(exception).strip()) or "sin mensaje"
                detail = f"Error interno inesperado ({type(exception).__name__}): {message}"
            lines.append(f"    Detalle : {detail}")
            if not isinstance(exception, GenerationFailure):
                trace = _redact_diagnostic(self.formatException(record.exc_info))
                lines.append(f"    Traza   : {trace}")
        lines.append(Style.RESET_ALL)
        return "\n".join(lines)


def render_banner(title: str, rows: tuple[tuple[str, str], ...], *, width: int = 72) -> str:
    """Render a boxed header of (label, value) rows, for the console's start-up banner."""
    inner = width - 2
    top = "┌" + "─" * inner + "┐"
    middle = "├" + "─" * inner + "┤"
    bottom = "└" + "─" * inner + "┘"
    lines = [top, "│" + title.center(inner) + "│", middle]
    for label, value in rows:
        text = f" {label}: {value}"
        lines.append("│" + text[:inner].ljust(inner) + "│")
    lines.append(bottom)
    return "\n".join(lines)


def print_banner(title: str, rows: tuple[tuple[str, str], ...]) -> None:
    """Print the start-up banner in cyan, to the console's own stream."""
    print(f"{Fore.CYAN}{render_banner(title, rows)}{Style.RESET_ALL}")


def configure_console_logging(level: int = logging.INFO) -> None:
    """Configure console logging."""
    use_utf8_output()
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
    job_id: str | None = None,
) -> None:
    """Handle the log user action operation for component."""
    logger.log(
        level,
        action,
        extra={
            "category": category,
            "user_id": user_id,
            "username": username,
            "job_id": job_id,
        },
        exc_info=exc_info,
    )
