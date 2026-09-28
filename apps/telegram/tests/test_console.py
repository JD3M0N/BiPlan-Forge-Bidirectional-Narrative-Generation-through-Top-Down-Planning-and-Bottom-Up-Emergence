import logging
import sys

import pytest
from asg_telegram.console import ConsoleFormatter, render_banner
from asg_telegram.contract import GenerationFailure
from colorama import Fore, Style


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


@pytest.mark.parametrize(
    ("category", "colour", "label"),
    [("acción", Fore.CYAN, "ACCIÓN"), ("éxito", Fore.GREEN, "ÉXITO")],
    ids=["action-line-is-cyan", "success-line-is-green"],
)
def test_console_formatter_renders_a_coloured_line_per_category(category, colour, label):
    record = make_record()
    record.category = category
    result = ConsoleFormatter().format(record)
    assert colour in result
    assert Style.RESET_ALL in result
    assert label in result
    assert "ana (123)" in result
    assert "inició una historia" in result


def test_console_formatter_shows_the_job_id():
    record = make_record()
    record.job_id = "3f2a9c1e-dead-beef"
    result = ConsoleFormatter().format(record)
    assert "3f2a9c1e" in result


def test_a_record_without_a_category_falls_back_by_level():
    record = make_record(level=logging.WARNING)
    record.category = None
    result = ConsoleFormatter().format(record)
    assert "ADVERTENCIA" in result


def test_console_formatter_shows_actionable_generation_failure():
    try:
        raise GenerationFailure(
            "El outline incumple el contrato.",
            code="ARTIFACT_VALIDATION_FAILED",
            stage="outline",
        )
    except GenerationFailure:
        record = make_record(level=logging.ERROR, message="falló la generación")
        record.exc_info = sys.exc_info()
    result = ConsoleFormatter().format(record)
    assert "ARTIFACT_VALIDATION_FAILED" in result
    assert "El outline incumple el contrato" in result
    assert "Etapa   : outline" in result


@pytest.mark.parametrize(
    "secret",
    ["token=super-secret", "no se pudo notificar con el token 123456789:AA" + "a" * 33],
    ids=["generic-credential-assignment", "telegram-bot-token"],
)
def test_console_formatter_redacts_credentials_from_tracebacks(secret):
    """A credential that reaches an unexpected traceback must never be printed."""
    try:
        raise ValueError(secret)
    except ValueError:
        record = make_record(level=logging.ERROR, message="falló la generación")
        record.exc_info = sys.exc_info()
    result = ConsoleFormatter().format(record)
    assert "ValueError" in result
    assert "Traza" in result
    assert "super-secret" not in result
    assert "123456789:AA" not in result
    assert "[REDACTED]" in result


def test_render_banner_fits_every_row_and_never_leaks_a_token():
    rows = (("Modelo", "gemini-3.5-flash-lite"), ("Clave", "configurada"))
    banner = render_banner("ASG Telegram", rows)
    assert "Modelo: gemini-3.5-flash-lite" in banner
    assert "AIza" not in banner
    for line in banner.splitlines():
        assert len(line) <= 72
