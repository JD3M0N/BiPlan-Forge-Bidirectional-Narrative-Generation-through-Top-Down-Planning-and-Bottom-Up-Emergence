"""Assemble the bot and run it: create stories with both models and compare them."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

from asg_core import use_utf8_output
from asg_core.files import atomic_write_text
from asg_evaluation.study import StudyRepository
from telegram import Update
from telegram.error import TelegramError
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, MessageHandler, filters

from .config import TelegramConfigurationError, load_settings
from .generator import GeneratorUnavailable, StagecraftGenerator
from .handlers import StoryBot
from .jobs import JobQueue, StoryWorker
from .pairs import OwnPairs
from .review import OwnReview
from .voting import Voting

LOGGER = logging.getLogger(__name__)
# /estudio, the blind study across participants, works but is not listed: it waits for enough
# stories and for the researcher to open the vote (asg-study open).
COMMANDS = [
    ("crear", "Crear una historia"),
    ("evaluar", "Comparar tus dos historias"),
    ("cancelar", "Cancelar lo que estés haciendo"),
    ("start", "Ver qué hace el bot"),
]


def build_application(token: str, queue: JobQueue, generator, study, pairs) -> Application:
    """Register every handler and start the worker with the application."""
    review = OwnReview(queue, pairs)
    voting = Voting(study) if study is not None else None
    worker = StoryWorker(None, queue, generator, study, pairs)
    bot = StoryBot(queue, worker, review, pairs)

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
        (("evaluar",), review.command),
        (("estudio",), voting.command if voting else _study_unavailable),
    ):
        application.add_handler(CommandHandler(names, handler, filters=filters.ChatType.PRIVATE))
    application.add_handler(CallbackQueryHandler(review.callback, pattern=r"^e:"))
    if voting:
        application.add_handler(CallbackQueryHandler(voting.callback, pattern=r"^v:[rka]:"))
    application.add_handler(CallbackQueryHandler(bot.callback))
    application.add_handler(
        MessageHandler(filters.ChatType.PRIVATE & filters.TEXT & ~filters.COMMAND, bot.text)
    )
    return application


async def _study_unavailable(update: Update, context) -> None:
    """Answer /estudio when the blind study could not be opened at start-up."""
    await update.effective_message.reply_text("El estudio a ciegas no está disponible ahora.")


def open_study(path: Path) -> StudyRepository | None:
    """Open the blind study, or run without it: it is hidden and must not stop the bot.

    A .env still pointing at a study retired in October (schema 4) stopped the bot at start-up.
    """
    try:
        return StudyRepository(path)
    except ValueError as exc:
        LOGGER.warning(
            "El estudio a ciegas no se abre (%s). El bot arranca sin /estudio; vacía "
            "ASG_EVALUATION_STUDY en el .env para usar uno nuevo.",
            exc,
        )
        return None


def parser() -> argparse.ArgumentParser:
    """Describe the command line: run the bot, or export the comparisons and stop."""
    result = argparse.ArgumentParser(
        prog="asg-telegram", description="Bot de Telegram del estudio: crear y comparar historias."
    )
    result.add_argument(
        "--export",
        type=Path,
        help="Escribe en este JSON las comparaciones de las propias historias y termina",
    )
    return result


def main(argv: list[str] | None = None) -> int:
    """Load the configuration and poll Telegram until interrupted, or export and stop."""
    use_utf8_output()
    args = parser().parse_args(argv)
    logging.basicConfig(format="%(asctime)s %(levelname)s %(message)s", level=logging.INFO)
    # httpx logs every request URL, and Telegram's URLs carry the bot token.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    try:
        settings = load_settings(need_token=not args.export)
        pairs = OwnPairs(settings.pairs_path)
        if args.export:
            atomic_write_text(args.export, pairs.export_json() + "\n")
            print(f"Comparaciones exportadas a {args.export}")
            return 0
        generator = StagecraftGenerator()
    except (TelegramConfigurationError, GeneratorUnavailable, ValueError) as exc:
        print(f"No se pudo arrancar el bot: {exc}", file=sys.stderr)
        return 2
    study = open_study(settings.study_path)
    LOGGER.info(
        "Bot listo. Comparaciones en %s; estudio %s (%s); historias en %s",
        settings.pairs_path,
        settings.study_path,
        study.info()["state"] if study else "no disponible",
        generator.settings.output_root,
    )
    queue = JobQueue(settings.queue_path)
    build_application(settings.token, queue, generator, study, pairs).run_polling(
        allowed_updates=Update.ALL_TYPES
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
