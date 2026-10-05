"""Application assembly and process entry point for the Telegram bot."""

from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path

from asg_evaluation.study import StudyRepository
from telegram import Update
from telegram.error import TelegramError
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, MessageHandler, filters

from .config import TelegramConfigurationError, load_settings
from .console import configure_console_logging, log_user_action, print_banner
from .contract import GeneratorUnavailable
from .generators import create_generator
from .handlers import TelegramStoryBot
from .queue import QueueRepository
from .study import StudyConversation

LOGGER = logging.getLogger(__name__)

__all__ = ["build_application", "main"]


def build_application(token: str, bot: TelegramStoryBot, *, on_ready=None) -> Application:
    """Build and register the complete python-telegram-bot application."""

    async def post_init(application) -> None:
        """Restore persisted queue state and greet the operator after start-up."""
        await bot.restore_queue(application)
        study_commands = (
            [
                ("evaluar", "Participar en la evaluación"),
                ("aportar", "Crear mi aportación al estudio"),
                ("pausa", "Pausar la evaluación"),
            ]
            if bot.study
            else []
        )
        try:
            await application.bot.set_my_commands(
                [
                    ("newstory", "Crear una historia"),
                    ("settings", "Configurar las opciones"),
                    ("cancel", "Cancelar la solicitud o evaluación actual"),
                    ("help", "Ver los comandos disponibles"),
                ]
                + study_commands
            )
        except TelegramError as exc:
            LOGGER.warning("No se pudieron publicar los comandos del bot: %s", exc)
        if on_ready is not None:
            me = await application.bot.get_me()
            on_ready(me.username)

    async def post_shutdown(application) -> None:
        """Record that the bot stopped, so the console shows a clean ending."""
        log_user_action(
            LOGGER, user_id=None, username=None, action="Bot detenido", category="sistema"
        )

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
        .post_shutdown(post_shutdown)
        .build()
    )
    application.add_handler(CommandHandler("start", bot.start))
    application.add_handler(CommandHandler("help", bot.help))
    application.add_handler(CommandHandler("newstory", bot.new_story))
    application.add_handler(CommandHandler("settings", bot.settings))
    application.add_handler(CommandHandler("opciones", bot.settings))
    application.add_handler(CommandHandler("cancel", bot.cancel))
    if bot.study:
        application.add_handler(CommandHandler("evaluar", bot.study.evaluate))
        application.add_handler(CommandHandler("aportar", bot.study.contribute))
        application.add_handler(CommandHandler("pausa", bot.study.pause))
        application.add_handler(CallbackQueryHandler(bot.study.callback, pattern=r"^study:"))
    application.add_handler(CallbackQueryHandler(bot.choose_format, pattern=r"^format:[a-z0-9-]+$"))
    application.add_handler(
        CallbackQueryHandler(bot.choose_mode, pattern=r"^mode:(free|guided|options)$")
    )
    application.add_handler(CallbackQueryHandler(bot.option_callback, pattern=r"^opt:"))
    application.add_handler(CallbackQueryHandler(bot.brief_callback, pattern=r"^brief:"))
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
    application.add_error_handler(bot.on_error)
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
        bot = TelegramStoryBot(
            generator,
            QueueRepository(settings.project_root / "Stories" / "telegram_queue.sqlite3"),
        )
        study_path = os.getenv("ASG_EVALUATION_STUDY", "").strip()
        if study_path:
            path = Path(study_path)
            if not path.is_absolute():
                path = settings.project_root / path
            if not path.is_file():
                raise ValueError("Crea el estudio antes de configurar ASG_EVALUATION_STUDY.")
            repository = StudyRepository(path)
            repository.info()
            bot.study = StudyConversation(repository, bot)
    except (TelegramConfigurationError, ValueError, GeneratorUnavailable) as exc:
        LOGGER.error("%s", exc)
        return 2

    def announce(username: str) -> None:
        """Print the start-up banner once the bot's own identity is known."""
        rows = (("Bot", f"@{username}"),) + generator.startup_details()
        print_banner("ASG Telegram", rows)
        LOGGER.info("Iniciando bot con el generador %s", generator.display_name)

    application = build_application(settings.telegram_token, bot, on_ready=announce)
    try:
        application.run_polling(allowed_updates=Update.ALL_TYPES)
    except TelegramError as exc:
        LOGGER.error("No se pudo conectar con Telegram: %s", exc)
        return 1
    except Exception:
        LOGGER.exception("El bot se detuvo por un error inesperado")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
