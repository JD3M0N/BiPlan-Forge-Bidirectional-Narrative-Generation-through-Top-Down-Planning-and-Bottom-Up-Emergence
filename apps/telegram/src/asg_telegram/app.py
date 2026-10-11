"""Application assembly and process entry point for the Telegram bot."""

from __future__ import annotations

import argparse
import asyncio
import logging

from asg_evaluation.study import StudyRepository
from telegram import Update
from telegram.error import TelegramError
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    TypeHandler,
    filters,
)

from .access import AccessGate
from .announcer import PhaseAnnouncer
from .config import TelegramConfigurationError, load_settings
from .console import configure_console_logging, log_user_action, print_banner
from .contract import GeneratorUnavailable
from .generators import create_generator
from .guide import ParticipantGuide
from .handlers import TelegramStoryBot
from .public_pool import GitHubPool, PoolPublisher
from .queue import QueueRepository
from .research_admin import ResearchAdmin
from .study import StudyConversation

LOGGER = logging.getLogger(__name__)

__all__ = ["build_application", "main"]

COMMANDS = [
    ("start", "Ver en qué paso estás y qué sigue"),
    ("newstory", "Crear una historia"),
    ("aportar", "Crear o reemplazar tu historia base"),
    ("evaluar", "Empezar o continuar la evaluación"),
    ("pausa", "Pausar la evaluación"),
    ("settings", "Configurar las opciones de generación"),
    ("cancel", "Cancelar la solicitud en curso"),
    ("help", "Ver los comandos disponibles"),
]


def build_application(token: str, bot: TelegramStoryBot, *, on_ready=None) -> Application:
    """Build and register the complete python-telegram-bot application."""

    async def post_init(application) -> None:
        """Restore persisted queue state and greet the operator after start-up."""
        await bot.restore_queue(application)
        try:
            await application.bot.set_my_commands(COMMANDS)
        except TelegramError as exc:
            LOGGER.warning("No se pudieron publicar los comandos del bot: %s", exc)
        if bot.guide is not None:
            bot.announcer_task = asyncio.create_task(PhaseAnnouncer(bot.guide).run(application.bot))
        _start_publisher(bot)
        if on_ready is not None:
            me = await application.bot.get_me()
            on_ready(me.username)

    async def post_stop(application) -> None:
        """Stop the phase announcer before the application shuts down."""
        await bot.stop_generation_tasks()
        for name in ("announcer_task", "publisher_task"):
            task = getattr(bot, name, None)
            if task is not None:
                task.cancel()

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
        .post_stop(post_stop)
        .post_shutdown(post_shutdown)
        .build()
    )
    if bot.gate is not None:
        application.add_handler(TypeHandler(Update, bot.gate.guard), group=-1)
    _register_research_handlers(application, bot)
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
    if bot.guide:
        application.add_handler(CallbackQueryHandler(bot.guide.callback, pattern=r"^guide:"))
    application.add_handler(CallbackQueryHandler(bot.choose_format, pattern=r"^format:[a-z0-9-]+$"))
    application.add_handler(
        CallbackQueryHandler(bot.choose_mode, pattern=r"^mode:(free|guided|options)$")
    )
    application.add_handler(CallbackQueryHandler(bot.option_callback, pattern=r"^opt:"))
    application.add_handler(CallbackQueryHandler(bot.brief_callback, pattern=r"^brief:"))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.text_input))
    application.add_error_handler(bot.on_error)
    bot.schedule = bot.background_task
    return application


def _start_publisher(bot) -> None:
    """Start an optional publisher independently of the generation queue."""
    publisher = getattr(bot, "pool_publisher", None)
    if publisher:
        bot.publisher_task = asyncio.create_task(publisher.run())


def _register_research_handlers(application, bot) -> None:
    """Attach private research tools when configured by the process entry point."""
    admin = getattr(bot, "research_admin", None)
    if admin:
        for command, handler in (
            ("publicacion", admin.consent),
            ("publicaciones_pendientes", admin.pending),
            ("revisar_historia", admin.review),
            ("aprobar_historia", admin.approve),
            ("exportar_estudio", admin.export),
        ):
            application.add_handler(CommandHandler(command, handler))
        application.add_handler(CallbackQueryHandler(admin.consent_answer, pattern=r"^publish:"))


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
        repository = StudyRepository(settings.study_path)
        study = repository.info()
        bot.study = StudyConversation(repository, bot)
        bot.guide = ParticipantGuide(bot)
        bot.gate = AccessGate(bot.queue, settings.access_key, bot.guide)
        bot.research_admin = ResearchAdmin(repository, settings.admin_ids)
        if settings.pool_repository and settings.pool_token:
            if not settings.admin_ids:
                raise TelegramConfigurationError("Configura TELEGRAM_ADMIN_IDS antes de publicar.")
            bot.pool_publisher = PoolPublisher(
                repository,
                GitHubPool(settings.pool_repository, settings.pool_token, settings.pool_branch),
            )
    except (TelegramConfigurationError, ValueError, GeneratorUnavailable) as exc:
        LOGGER.error("%s", exc)
        return 2

    def announce(username: str) -> None:
        """Print the start-up banner once the bot's own identity is known."""
        rows = (
            ("Bot", f"@{username}"),
            ("Estudio", f"{study['id']} · fase {study['state']}"),
            ("Acceso", "clave compartida (TELEGRAM_ACCESS_KEY)"),
        ) + generator.startup_details()
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
