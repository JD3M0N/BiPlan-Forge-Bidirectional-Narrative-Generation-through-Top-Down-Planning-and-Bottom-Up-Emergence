import logging
import sys

from colorama import Fore, Style

from asg_telegram.console import ConsoleFormatter
from asg_top_down.errors import ArtifactValidationError


def make_record(level=logging.INFO, message="inició una historia"):
    record = logging.LogRecord(
        "asg_telegram",
        level,
        __file__,
        1,
        message,
        (),
        None,
    )
    record.category = "acción"
    record.user_id = 123
    record.username = "ana"
    return record


def test_console_formatter_shows_clear_colored_user_block():
    result = ConsoleFormatter().format(make_record())
    assert Fore.CYAN in result
    assert Style.RESET_ALL in result
    assert "ACCIÓN" in result
    assert "Usuario : 123 (ana)" in result
    assert "Acción  : inició una historia" in result


def test_console_formatter_does_not_add_secrets():
    result = ConsoleFormatter().format(make_record(message="ejecutó /start"))
    assert "TELEGRAM_BOT_TOKEN" not in result
    assert "GEMINI_API_KEY" not in result


def test_console_formatter_uses_green_for_success():
    record = make_record(message="historia entregada")
    record.category = "éxito"
    result = ConsoleFormatter().format(record)
    assert Fore.GREEN in result
    assert "ÉXITO" in result


def test_console_formatter_shows_actionable_asg_error():
    try:
        raise ArtifactValidationError(
            "El outline incumple el contrato.", stage="outline",
            details={"artifact": "outline"},
        )
    except ArtifactValidationError:
        record = make_record(level=logging.ERROR, message="falló la generación")
        record.exc_info = sys.exc_info()
    result = ConsoleFormatter().format(record)
    assert "ARTIFACT_VALIDATION_FAILED" in result
    assert "El outline incumple el contrato" in result
    assert "Etapa   : outline" in result


def test_console_formatter_redacts_unexpected_traceback_credentials():
    try:
        raise ValueError("token=super-secret")
    except ValueError:
        record = make_record(level=logging.ERROR, message="falló la generación")
        record.exc_info = sys.exc_info()
    result = ConsoleFormatter().format(record)
    assert "ValueError" in result
    assert "Traza" in result
    assert "super-secret" not in result
    assert "[REDACTED]" in result
