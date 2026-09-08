"""Telegram conversation and evaluation handlers."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from asg_evaluation import METRICS, add_evaluation
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from .console import log_user_action
from .contract import StoryGeneratorAdapter
from .generation import GenerationCoordinator
from .prompts import (
    GUIDED_FIELDS,
    METRIC_EXPLANATIONS,
    PROFILE_FIELD,
    build_guided_prompt,
    guided_question,
    validate_guided_value,
)
from .queue import QueueRepository
from .states import ConversationState

LOGGER = logging.getLogger(__name__)
MAX_EVALUATION_RETRIES = 3
EXAMPLE_PROMPT = (
    "Escribe un relato de ciencia ficción de unas 1800 palabras sobre una "
    "cartógrafa que descubre un mensaje en las estrellas. Tono melancólico "
    "y final esperanzador."
)


def _user_log(update: Update, action: str, category: str = "acción") -> None:
    """Log an action with the best available Telegram user identity."""
    user = update.effective_user
    if user is None:
        log_user_action(
            LOGGER,
            user_id=None,
            username=None,
            action=action,
            category=category,
        )
        return
    readable = user.username or user.full_name or "sin nombre"
    log_user_action(
        LOGGER,
        user_id=user.id,
        username=readable,
        action=action,
        category=category,
    )


def _mode_keyboard() -> InlineKeyboardMarkup:
    """Build the free-form versus guided prompt selection keyboard."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Prompt libre", callback_data="mode:free"),
                InlineKeyboardButton("Asistente guiado", callback_data="mode:guided"),
            ]
        ]
    )


def _score_keyboard(metric: str) -> InlineKeyboardMarkup:
    """Build a two-row keyboard containing scores one through ten."""
    rows = [
        [
            InlineKeyboardButton(str(score), callback_data=f"score:{metric}:{score}")
            for score in range(start, min(start + 5, 11))
        ]
        for start in (1, 6)
    ]
    return InlineKeyboardMarkup(rows)


def _score_summary(scores: dict[str, int]) -> str:
    """List every recorded metric score as one bulleted Spanish line each."""
    return "\n".join(f"• {metric}: {scores[metric]}/10" for metric in METRICS)


def _evaluator_name(user) -> str:
    """Build the persisted evaluator identifier for a Telegram user."""
    readable = user.username or user.full_name or "sin nombre"
    return f"telegram:{user.id} ({readable})"


class TelegramStoryBot(GenerationCoordinator):
    """Handle Telegram conversations around generation and evaluation."""

    def __init__(
        self, generator: StoryGeneratorAdapter, queue: QueueRepository | None = None
    ) -> None:
        """Configure conversation handlers with their generation coordinator."""
        super().__init__(generator, queue)

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Welcome a user and advertise the primary commands."""
        _user_log(update, "ejecutó /start")
        await update.effective_message.reply_text(
            "¡Hola! Puedo crear historias con el enfoque "
            f"{self.generator.display_name} y luego recoger tu evaluación.\n\n"
            "Usa /newstory para comenzar o /help para ver los comandos."
        )

    async def help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Display the supported bot commands."""
        _user_log(update, "ejecutó /help")
        await update.effective_message.reply_text(
            "/newstory — crear una historia\n"
            "/cancel — abandonar la solicitud o evaluación actual\n"
            "/help — mostrar esta ayuda"
        )

    async def new_story(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Start prompt collection unless the user already has active work."""
        user_id = update.effective_user.id
        _user_log(update, "ejecutó /newstory")
        if user_id in self.active_users:
            _user_log(update, "intentó iniciar otra generación mientras tenía una activa")
            await update.effective_message.reply_text(
                "Ya estoy generando una historia para ti. Espera a que termine."
            )
            return
        context.user_data.clear()
        context.user_data["state"] = ConversationState.CHOOSE_MODE
        await update.effective_message.reply_text(
            "¿Cómo quieres describir la historia?",
            reply_markup=_mode_keyboard(),
        )

    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Cancel a waiting job or clear an inactive conversation state."""
        user_id = update.effective_user.id
        _user_log(update, "ejecutó /cancel")
        outcome = self.queue.cancel_user(user_id) if self.queue else None
        if outcome == "cancelled":
            self.active_users.discard(user_id)
            context.user_data.clear()
            await update.effective_message.reply_text(
                "Tu solicitud fue retirada de la cola. Puedes usar /newstory cuando quieras."
            )
            await self._refresh_queue(context.application)
            return
        if outcome == "requested":
            await update.effective_message.reply_text(
                "Pedí detener la generación. Terminará en cuanto acabe la etapa en curso."
            )
            return
        if user_id in self.active_users:
            await update.effective_message.reply_text(
                "La generación o entrega ya está en curso y no puede cancelarse. "
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

    async def choose_mode(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Activate free-form or guided prompt collection."""
        query = update.callback_query
        await query.answer()
        if context.user_data.get("state") != ConversationState.CHOOSE_MODE:
            await query.edit_message_text("Esta selección ya no está activa.")
            return
        mode = query.data.split(":", 1)[1]
        _user_log(update, f"seleccionó el modo {mode}")
        if mode == "free":
            context.user_data["state"] = ConversationState.FREE_PROMPT
            await query.edit_message_text(
                f"Envía una descripción completa.\n\nEjemplo:\n{EXAMPLE_PROMPT}"
            )
            return
        context.user_data.update(state=ConversationState.GUIDED, guided_index=0, guided_values={})
        await query.edit_message_text(guided_question(0, self.generator.profiles))

    async def text_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Route text according to the user's current conversation state."""
        state = context.user_data.get("state")
        text = update.effective_message.text
        if state == ConversationState.FREE_PROMPT:
            _user_log(update, "envió un prompt libre")
            if not text.strip():
                await update.effective_message.reply_text("La descripción no puede estar vacía.")
                return
            await self._launch_generation(update, context, text.strip())
        elif state == ConversationState.GUIDED:
            await self._guided_input(update, context, text)
        elif state == ConversationState.EVALUATING:
            _user_log(update, "envió texto durante la evaluación")
            await update.effective_message.reply_text(
                "Selecciona una puntuación usando los botones del 1 al 10."
            )
        else:
            await update.effective_message.reply_text("Usa /newstory para crear una historia.")

    async def _guided_input(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE, text: str
    ) -> None:
        """Validate one guided field and advance or launch generation."""
        index = context.user_data["guided_index"]
        field, _ = GUIDED_FIELDS[index]
        _user_log(update, f"respondió el campo guiado {field}")
        profiles = self.generator.profiles
        try:
            value = validate_guided_value(field, text, profiles)
        except ValueError as exc:
            await update.effective_message.reply_text(str(exc))
            return
        context.user_data["guided_values"][field] = value
        index += 1
        context.user_data["guided_index"] = index
        if index < len(GUIDED_FIELDS):
            await update.effective_message.reply_text(guided_question(index, profiles))
            return
        values = context.user_data["guided_values"]
        chosen = values[PROFILE_FIELD]
        await self._launch_generation(
            update,
            context,
            build_guided_prompt(values, profiles),
            next((option.value for option in profiles if option.value == chosen), None),
        )

    async def _begin_evaluation(self, context, chat_id: int, user, story_directory: Path) -> None:
        """Initialize evaluation state after a successful story delivery."""
        context.user_data.update(
            state=ConversationState.EVALUATING,
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

    async def _ask_metric(self, context, chat_id: int) -> None:
        """Send the explanation and score keyboard for the current metric."""
        metric = METRICS[context.user_data["metric_index"]]
        explanation = METRIC_EXPLANATIONS[metric].message()
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"{explanation}\n\nElige una puntuación:",
            parse_mode=ParseMode.HTML,
            reply_markup=_score_keyboard(metric),
        )

    async def score(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Validate one score and advance or persist the evaluation."""
        query = update.callback_query
        if context.user_data.get("state") != ConversationState.EVALUATING:
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
        explanation = METRIC_EXPLANATIONS[metric].message()
        await query.edit_message_text(
            f"{explanation}\n\nPuntuación elegida: <b>{score}/10</b>",
            parse_mode=ParseMode.HTML,
        )
        context.user_data["metric_index"] += 1
        if context.user_data["metric_index"] < len(METRICS):
            await self._ask_metric(context, update.effective_chat.id)
            return
        await self._save_evaluation(update, context)

    async def _save_evaluation(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Persist a complete evaluation and reset the user conversation."""
        scores = dict(context.user_data["scores"])
        story_directory = context.user_data["story_directory"]
        evaluator = context.user_data["evaluator"]
        try:
            await asyncio.to_thread(add_evaluation, story_directory, evaluator, scores)
        except Exception:
            LOGGER.exception("No se pudo guardar una evaluación")
            attempts = context.user_data.get("save_attempts", 0) + 1
            if attempts >= MAX_EVALUATION_RETRIES:
                context.user_data.clear()
                await update.effective_message.reply_text(
                    "No pude guardar la evaluación tras varios intentos. Estas fueron tus "
                    f"puntuaciones:\n{_score_summary(scores)}\n\nAvisa al operador y usa "
                    "/newstory cuando quieras continuar."
                )
                return
            context.user_data["save_attempts"] = attempts
            await update.effective_message.reply_text(
                "No pude guardar la evaluación. Intenta responder de nuevo."
            )
            context.user_data["metric_index"] = len(METRICS) - 1
            context.user_data["scores"].pop(METRICS[-1], None)
            await self._ask_metric(context, update.effective_chat.id)
            return
        summary = _score_summary(scores)
        context.user_data.clear()
        _user_log(update, "completó y guardó la evaluación")
        await update.effective_message.reply_text(
            f"¡Gracias! Evaluación guardada:\n{summary}\n\nUsa /newstory para crear otra historia."
        )
