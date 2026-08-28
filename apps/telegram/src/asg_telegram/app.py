"""Application assembly and process entry point for the Telegram bot."""

from __future__ import annotations

import argparse
import logging

from telegram import Update
from telegram.error import TelegramError
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, MessageHandler, filters

from .config import TelegramConfigurationError, load_settings
from .console import configure_console_logging
from .generators import create_generator
from .handlers import TelegramStoryBot, _evaluator_name
from .queue import QueueRepository

LOGGER = logging.getLogger(__name__)

__all__ = ["TelegramStoryBot", "_evaluator_name", "build_application", "main"]


def build_application(token: str, bot: TelegramStoryBot) -> Application:
    """Build and register the complete python-telegram-bot application."""

    async def post_init(application) -> None:
        """Restore persisted queue state after Telegram initialization."""
        await bot.restore_queue(application)

    application = (
        Application.builder()
        .token(token)
        .connect_timeout(15)
        .read_timeout(30)
        .write_timeout(30)
        .media_write_timeout(60)
        .pool_timeout(10)
        .concurrent_updates(True)
        .post_init(post_init)
        .build()
    )
    application.add_handler(CommandHandler("start", bot.start))
    application.add_handler(CommandHandler("help", bot.help))
    application.add_handler(CommandHandler("newstory", bot.new_story))
    application.add_handler(CommandHandler("cancel", bot.cancel))
    application.add_handler(CallbackQueryHandler(bot.choose_mode, pattern=r"^mode:(free|guided)$"))
    application.add_handler(
        CallbackQueryHandler(
            bot.score,
            pattern=(
                r"^score:(coherence|pacing|creativity|engagement|relevance|"
                r"satisfaction):(?:10|[1-9])$"
            ),
        )
    )
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.text_input))
    return application


def parser() -> argparse.ArgumentParser:
    """Build the in-process Telegram bot command-line parser."""
    return argparse.ArgumentParser(description="Ejecuta el bot ASG Telegram en esta consola")


def main(argv: list[str] | None = None) -> int:
    """Configure and run the polling bot, returning a process status code."""
    parser().parse_args(argv)
    configure_console_logging()
    try:
        settings = load_settings()
        generator = create_generator(settings.generator_name)
        application = build_application(
            settings.telegram_token,
            TelegramStoryBot(
                generator,
                QueueRepository(settings.project_root / "Stories" / "telegram_queue.sqlite3"),
            ),
        )
    except (TelegramConfigurationError, ValueError) as exc:
        LOGGER.error("%s", exc)
        return 2
    LOGGER.info("Iniciando bot con el generador %s", generator.display_name)
    try:
        application.run_polling(allowed_updates=Update.ALL_TYPES)
    except TelegramError as exc:
        LOGGER.error("No se pudo conectar con Telegram: %s", exc)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
