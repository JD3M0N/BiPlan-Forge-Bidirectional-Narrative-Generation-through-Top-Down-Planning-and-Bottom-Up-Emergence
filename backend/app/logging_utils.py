import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from app.config import Settings


APP_LOGGER_NAME = "story_writers"
AUDIT_LOGGER_NAME = "story_writers.audit"
PIPELINE_LOGGER_NAME = "story_writers.pipeline"
PIPELINE_LOG_LIMIT = 100


class LastLinesFileHandler(logging.Handler):
    def __init__(self, filename: Path, max_lines: int) -> None:
        super().__init__()
        self.filename = filename
        self.max_lines = max_lines

    def emit(self, record: logging.LogRecord) -> None:
        try:
            message = self.format(record)
            lines = []
            if self.filename.exists():
                lines = self.filename.read_text(encoding="utf-8").splitlines()
            lines.append(message)
            self.filename.write_text(
                "\n".join(lines[-self.max_lines :]) + "\n",
                encoding="utf-8",
            )
        except Exception:
            self.handleError(record)


def _clear_handlers(logger: logging.Logger) -> None:
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
        handler.close()


def configure_logging(settings: Settings) -> None:
    log_dir = Path(settings.log_dir)
    if not log_dir.is_absolute():
        log_dir = Path.cwd() / log_dir
    log_dir.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    level = getattr(logging, settings.log_level.upper(), logging.INFO)

    app_logger = logging.getLogger(APP_LOGGER_NAME)
    audit_logger = logging.getLogger(AUDIT_LOGGER_NAME)
    pipeline_logger = logging.getLogger(PIPELINE_LOGGER_NAME)
    root_logger = logging.getLogger()

    for logger in (app_logger, audit_logger, pipeline_logger, root_logger):
        _clear_handlers(logger)

    app_logger.setLevel(level)
    audit_logger.setLevel(logging.INFO)
    pipeline_logger.setLevel(logging.INFO)
    root_logger.setLevel(level)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)

    pipeline_console_handler = logging.StreamHandler()
    pipeline_console_handler.setLevel(logging.INFO)
    pipeline_console_handler.setFormatter(
        logging.Formatter("%(asctime)s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    )

    app_file_handler = RotatingFileHandler(
        log_dir / "app.log",
        maxBytes=1_000_000,
        backupCount=3,
        encoding="utf-8",
    )
    app_file_handler.setLevel(level)
    app_file_handler.setFormatter(formatter)

    audit_file_handler = RotatingFileHandler(
        log_dir / "audit.log",
        maxBytes=1_000_000,
        backupCount=3,
        encoding="utf-8",
    )
    audit_file_handler.setLevel(logging.INFO)
    audit_file_handler.setFormatter(formatter)

    pipeline_file_handler = LastLinesFileHandler(log_dir / "pipeline.log.txt", max_lines=PIPELINE_LOG_LIMIT)
    pipeline_file_handler.setLevel(logging.INFO)
    pipeline_file_handler.setFormatter(
        logging.Formatter("%(asctime)s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    )

    app_logger.addHandler(console_handler)
    app_logger.addHandler(app_file_handler)
    app_logger.propagate = False

    audit_logger.addHandler(audit_file_handler)
    audit_logger.addHandler(console_handler)
    audit_logger.propagate = False

    pipeline_logger.addHandler(pipeline_console_handler)
    pipeline_logger.addHandler(pipeline_file_handler)
    pipeline_logger.propagate = False

    root_logger.addHandler(console_handler)

    logging.getLogger("httpx").setLevel(logging.WARNING)


def get_logger(name: str | None = None) -> logging.Logger:
    base_name = APP_LOGGER_NAME if not name else f"{APP_LOGGER_NAME}.{name}"
    return logging.getLogger(base_name)


def get_audit_logger() -> logging.Logger:
    return logging.getLogger(AUDIT_LOGGER_NAME)


def get_pipeline_logger() -> logging.Logger:
    return logging.getLogger(PIPELINE_LOGGER_NAME)
