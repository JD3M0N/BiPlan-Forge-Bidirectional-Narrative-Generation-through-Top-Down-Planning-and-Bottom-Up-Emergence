"""Bot de Telegram para generar historias y registrar evaluaciones."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from asg_evaluation import METRICS, add_evaluation
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import TelegramError
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from .config import TelegramConfigurationError, load_settings
from .generators import StoryGenerator, create_generator
from .prompts import (
    GUIDED_FIELDS,
    METRIC_EXPLANATIONS,
    build_guided_prompt,
    split_story,
    validate_guided_value,
)

LOGGER = logging.getLogger(__name__)
EXAMPLE_PROMPT = (
    "Escribe un relato de ciencia ficción de unas 1800 palabras sobre una "
    "cartógrafa que descubre un mensaje en las estrellas. Tono melancólico "
    "y final esperanzador."
)


def _user_log(update: Update, action: str) -> None:
    user = update.effective_user
    if user is None:
        LOGGER.info("Acción sin usuario: %s", action)
        return
    readable = user.username or user.full_name or "sin nombre"
    LOGGER.info("Usuario %s (%s) — %s", user.id, readable, action)


def _mode_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[
            InlineKeyboardButton("Prompt libre", callback_data="mode:free"),
            InlineKeyboardButton("Asistente guiado", callback_data="mode:guided"),
        ]]
    )


def _score_keyboard(metric: str) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(str(score), callback_data=f"score:{metric}:{score}")
            for score in range(start, min(start + 5, 11))
        ]
        for start in (1, 6)
    ]
    return InlineKeyboardMarkup(rows)


class TelegramStoryBot:
    def __init__(self, generator: StoryGenerator) -> None:
        self.generator = generator
        self.active_users: set[int] = set()

    async def start(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        _user_log(update, "ejecutó /start")
        await update.effective_message.reply_text(
            "¡Hola! Puedo crear historias con el enfoque "
            f"{self.generator.display_name} y luego recoger tu evaluación.\n\n"
            "Usa /newstory para comenzar o /help para ver los comandos."
        )

    async def help(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        _user_log(update, "ejecutó /help")
        await update.effective_message.reply_text(
            "/newstory — crear una historia\n"
            "/cancel — abandonar la solicitud o evaluación actual\n"
            "/help — mostrar esta ayuda"
        )

    async def new_story(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        user_id = update.effective_user.id
        _user_log(update, "ejecutó /newstory")
        if user_id in self.active_users:
            _user_log(update, "intentó iniciar otra generación mientras tenía una activa")
            await update.effective_message.reply_text(
                "Ya estoy generando una historia para ti. Espera a que termine."
            )
            return
        context.user_data.clear()
        context.user_data["state"] = "choose_mode"
        await update.effective_message.reply_text(
            "¿Cómo quieres describir la historia?",
            reply_markup=_mode_keyboard(),
        )

    async def cancel(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        user_id = update.effective_user.id
        _user_log(update, "ejecutó /cancel")
        if user_id in self.active_users:
            await update.effective_message.reply_text(
                "La generación ya está en curso y no puede cancelarse. "
                "Te avisaré cuando termine."
            )
            return
        had_state = bool(context.user_data.get("state"))
        context.user_data.clear()
        await update.effective_message.reply_text(
            "Proceso cancelado. Puedes usar /newstory cuando quieras."
            if had_state
            else "No hay ningún proceso activo."
        )

    async def choose_mode(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        query = update.callback_query
        await query.answer()
        if context.user_data.get("state") != "choose_mode":
            await query.edit_message_text("Esta selección ya no está activa.")
            return
        mode = query.data.split(":", 1)[1]
        _user_log(update, f"seleccionó el modo {mode}")
        if mode == "free":
            context.user_data["state"] = "free_prompt"
            await query.edit_message_text(
                f"Envía una descripción completa.\n\nEjemplo:\n{EXAMPLE_PROMPT}"
            )
            return
        context.user_data.update(
            state="guided",
            guided_index=0,
            guided_values={},
        )
        await query.edit_message_text(GUIDED_FIELDS[0][1])

    async def text_input(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        state = context.user_data.get("state")
        text = update.effective_message.text
        if state == "free_prompt":
            _user_log(update, "envió un prompt libre")
            if not text.strip():
                await update.effective_message.reply_text(
                    "La descripción no puede estar vacía."
                )
                return
            await self._launch_generation(update, context, text.strip())
        elif state == "guided":
            await self._guided_input(update, context, text)
        elif state == "evaluating":
            _user_log(update, "envió texto durante la evaluación")
            await update.effective_message.reply_text(
                "Selecciona una puntuación usando los botones del 1 al 10."
            )
        else:
            await update.effective_message.reply_text(
                "Usa /newstory para crear una historia."
            )

    async def _guided_input(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE, text: str
    ) -> None:
        index = context.user_data["guided_index"]
        field, _ = GUIDED_FIELDS[index]
        _user_log(update, f"respondió el campo guiado {field}")
        try:
            value = validate_guided_value(field, text)
        except ValueError as exc:
            await update.effective_message.reply_text(str(exc))
            return
        context.user_data["guided_values"][field] = value
        index += 1
        context.user_data["guided_index"] = index
        if index < len(GUIDED_FIELDS):
            await update.effective_message.reply_text(GUIDED_FIELDS[index][1])
            return
        prompt = build_guided_prompt(context.user_data["guided_values"])
        await self._launch_generation(update, context, prompt)

    async def _launch_generation(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE, prompt: str
    ) -> None:
        user_id = update.effective_user.id
        if user_id in self.active_users:
            await update.effective_message.reply_text(
                "Ya hay una generación activa para ti."
            )
            return
        self.active_users.add(user_id)
        _user_log(update, f"inició una generación {self.generator.display_name}")
        context.user_data.clear()
        context.user_data["state"] = "generating"
        await update.effective_message.reply_text(
            f"Generando con {self.generator.display_name}. Puede tardar unos minutos…"
        )
        context.application.create_task(
            self._generate_and_deliver(
                context=context,
                chat_id=update.effective_chat.id,
                user=update.effective_user,
                prompt=prompt,
            ),
            update=update,
        )

    async def _generate_and_deliver(
        self, *, context, chat_id: int, user, prompt: str
    ) -> None:
        try:
            story_directory = await asyncio.to_thread(
                self.generator.generate, prompt
            )
            LOGGER.info(
                "Usuario %s — generación terminada en %s",
                user.id,
                story_directory,
            )
            story_path = Path(story_directory) / "story.md"
            story = await asyncio.to_thread(
                story_path.read_text, encoding="utf-8"
            )
            for chunk in split_story(story):
                await context.bot.send_message(chat_id=chat_id, text=chunk)
            with story_path.open("rb") as document:
                await context.bot.send_document(
                    chat_id=chat_id,
                    document=document,
                    filename=story_path.name,
                    caption="Historia completa en formato Markdown.",
                )
            LOGGER.info("Usuario %s — historia entregada por Telegram", user.id)
            context.user_data.update(
                state="evaluating",
                story_directory=str(story_directory),
                metric_index=0,
                scores={},
                evaluator=_evaluator_name(user),
            )
            await context.bot.send_message(
                chat_id=chat_id,
                text=(
                    "Ahora evalúa la historia. Cada parámetro se puntúa del "
                    "1 (mínimo) al 10 (máximo). Usa /cancel si quieres abandonar."
                ),
            )
            await self._ask_metric(context, chat_id)
        except Exception:
            LOGGER.exception(
                "Usuario %s — falló la generación o entrega de una historia",
                user.id,
            )
            context.user_data.clear()
            await context.bot.send_message(
                chat_id=chat_id,
                text=(
                    "No pude generar o entregar la historia. Comprueba la "
                    "configuración y vuelve a intentarlo más tarde."
                ),
            )
        finally:
            self.active_users.discard(user.id)

    async def _ask_metric(self, context, chat_id: int) -> None:
        metric = METRICS[context.user_data["metric_index"]]
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"{METRIC_EXPLANATIONS[metric]}\n\nElige una puntuación:",
            reply_markup=_score_keyboard(metric),
        )

    async def score(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        query = update.callback_query
        if context.user_data.get("state") != "evaluating":
            await query.answer()
            await query.edit_message_text("Esta evaluación ya no está activa.")
            return
        _, metric, raw_score = query.data.split(":")
        expected = METRICS[context.user_data["metric_index"]]
        if metric != expected:
            await query.answer("Esa pregunta ya fue respondida.", show_alert=True)
            return
        score = int(raw_score)
        if not 1 <= score <= 10:
            await query.answer("La puntuación debe estar entre 1 y 10.", show_alert=True)
            return
        await query.answer()
        _user_log(update, f"puntuó {metric} con {score}/10")
        context.user_data["scores"][metric] = score
        await query.edit_message_text(
            f"{METRIC_EXPLANATIONS[metric]}\n\nPuntuación: {score}/10"
        )
        context.user_data["metric_index"] += 1
        if context.user_data["metric_index"] < len(METRICS):
            await self._ask_metric(context, update.effective_chat.id)
            return
        await self._save_evaluation(update, context)

    async def _save_evaluation(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        scores = dict(context.user_data["scores"])
        story_directory = context.user_data["story_directory"]
        evaluator = context.user_data["evaluator"]
        try:
            await asyncio.to_thread(
                add_evaluation, story_directory, evaluator, scores
            )
        except Exception:
            LOGGER.exception("No se pudo guardar una evaluación")
            await update.effective_message.reply_text(
                "No pude guardar la evaluación. Intenta responder de nuevo."
            )
            context.user_data["metric_index"] = len(METRICS) - 1
            context.user_data["scores"].pop(METRICS[-1], None)
            await self._ask_metric(context, update.effective_chat.id)
            return
        summary = "\n".join(
            f"• {metric}: {scores[metric]}/10" for metric in METRICS
        )
        context.user_data.clear()
        _user_log(update, "completó y guardó la evaluación")
        await update.effective_message.reply_text(
            f"¡Gracias! Evaluación guardada:\n{summary}\n\n"
            "Usa /newstory para crear otra historia."
        )


def _evaluator_name(user) -> str:
    readable = user.username or user.full_name or "sin nombre"
    return f"telegram:{user.id} ({readable})"


def build_application(token: str, bot: TelegramStoryBot) -> Application:
    application = (
        Application.builder().token(token).concurrent_updates(True).build()
    )
    application.add_handler(CommandHandler("start", bot.start))
    application.add_handler(CommandHandler("help", bot.help))
    application.add_handler(CommandHandler("newstory", bot.new_story))
    application.add_handler(CommandHandler("cancel", bot.cancel))
    application.add_handler(
        CallbackQueryHandler(bot.choose_mode, pattern=r"^mode:(free|guided)$")
    )
    application.add_handler(
        CallbackQueryHandler(
            bot.score,
            pattern=r"^score:(coherence|pacing|creativity|engagement|relevance|satisfaction):(?:10|[1-9])$",
        )
    )
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, bot.text_input)
    )
    return application


def main() -> int:
    logging.basicConfig(
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        level=logging.INFO,
    )
    try:
        settings = load_settings()
        generator = create_generator(settings.generator_name)
        application = build_application(
            settings.telegram_token, TelegramStoryBot(generator)
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
