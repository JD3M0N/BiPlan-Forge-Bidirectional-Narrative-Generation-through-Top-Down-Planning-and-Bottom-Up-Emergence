"""Assemble the bot and run it: create stories and compare them, nothing else."""

from __future__ import annotations

import asyncio
import logging
import sys

from asg_core import use_utf8_output
from asg_evaluation.study import StudyRepository
from telegram import Update
from telegram.error import TelegramError
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, MessageHandler, filters

from .config import TelegramConfigurationError, load_settings
from .generator import GeneratorUnavailable, StagecraftGenerator
from .handlers import StoryBot
from .jobs import JobQueue, StoryWorker
from .voting import Voting

LOGGER = logging.getLogger(__name__)
COMMANDS = [
    ("crear", "Crear una historia"),
    ("evaluar", "Comparar historias"),
    ("cancelar", "Cancelar lo que estés haciendo"),
    ("start", "Ver qué hace el bot"),
]


def build_application(token: str, queue: JobQueue, generator, study) -> Application:
    """Register every handler and start the worker with the application."""
    voting = Voting(study)
    worker = StoryWorker(None, queue, generator, study)
    bot = StoryBot(queue, worker, voting)

    async def post_init(app: Application) -> None:
        """Publish the command list and launch the single generation worker."""
        try:
            await app.bot.set_my_commands(COMMANDS)
        except TelegramError as exc:
            LOGGER.warning("No se pudieron publicar los comandos: %s", exc)
        app.bot_data["worker"] = asyncio.create_task(worker.run())

    async def post_stop(app: Application) -> None:
        """Stop the worker; an interrupted run is requeued on the next start."""
        task = app.bot_data.get("worker")
        if task:
            task.cancel()

    application = (
        Application.builder().token(token).post_init(post_init).post_stop(post_stop).build()
    )
    worker.bot = application.bot
    for names, handler in (
        (("start", "help", "ayuda"), bot.start),
        (("crear", "newstory"), bot.create),
        (("cancelar", "cancel"), bot.cancel),
        (("evaluar",), voting.command),
    ):
        application.add_handler(CommandHandler(names, handler, filters=filters.ChatType.PRIVATE))
    application.add_handler(CallbackQueryHandler(voting.callback, pattern=r"^v:[rka]:"))
    application.add_handler(CallbackQueryHandler(bot.callback))
    application.add_handler(
        MessageHandler(filters.ChatType.PRIVATE & filters.TEXT & ~filters.COMMAND, bot.text)
    )
    return application


def main() -> int:
    """Load the configuration and poll Telegram until interrupted."""
    use_utf8_output()
    logging.basicConfig(format="%(asctime)s %(levelname)s %(message)s", level=logging.INFO)
    # httpx logs every request URL, and Telegram's URLs carry the bot token.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    try:
        settings = load_settings()
        generator = StagecraftGenerator()
        study = StudyRepository(settings.study_path)
    except (TelegramConfigurationError, GeneratorUnavailable, ValueError) as exc:
        print(f"No se pudo arrancar el bot: {exc}", file=sys.stderr)
        return 2
    LOGGER.info(
        "Bot listo. Estudio %s (%s); historias en %s",
        settings.study_path,
        study.info()["state"],
        generator.settings.output_root,
    )
    queue = JobQueue(settings.queue_path)
    build_application(settings.token, queue, generator, study).run_polling(
        allowed_updates=Update.ALL_TYPES
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
