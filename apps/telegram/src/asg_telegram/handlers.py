"""Story creation: four ways in (free or guided, Top-Down or hybrid), and the same idea again."""

from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from . import wizard
from .generator import BRIEF_LIMITS, METHODS, StoryOutline
from .guide import CHOOSE, CREATE, MODES, WELCOME, next_step, option_label, other_format

INACTIVE = "Este botón ya no está activo. Empieza con /crear."


class StoryBot:
    """Collect one story request per participant and hand it to the worker."""

    def __init__(self, queue, worker, review, pairs) -> None:
        """Wire the conversation to the queue, the worker and the comparison of own stories."""
        self.queue = queue
        self.worker = worker
        self.review = review
        self.pairs = pairs

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Explain what the bot does and recommend the participant's next step."""
        context.user_data.clear()
        _, markup = next_step(self.queue, self.pairs, update.effective_user.id)
        await update.effective_message.reply_text(WELCOME, reply_markup=markup)

    async def create(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Offer the four ways to create a story."""
        context.user_data.clear()
        await update.effective_message.reply_text(CHOOSE, reply_markup=CREATE)

    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Drop the conversation and cancel the participant's request, if any."""
        context.user_data.clear()
        status = self.queue.cancel(update.effective_user.id)
        text = {
            "queued": "Solicitud cancelada.",
            "running": "Cancelando la generación en curso…",
        }.get(status, "Cancelado.")
        await update.effective_message.reply_text(text)

    async def callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle the creation menu, the same-idea button and the wizard."""
        query = update.callback_query
        data = query.data
        await query.answer()
        if data == "c:menu":
            context.user_data.clear()
            await query.edit_message_text(CHOOSE, reply_markup=CREATE)
        elif data.startswith("c:o:"):
            await self._choose(query, context, *data.split(":")[2:])
        elif data.startswith("c:same:"):
            await self._same_idea(update, context, int(data.split(":")[2]))
        elif data.startswith("w:") and "wizard" in context.user_data:
            reply = wizard.press(context.user_data["wizard"], data[2:])
            await query.edit_message_text(reply.text, reply_markup=reply.keyboard)
            if reply.outline is not None:
                await self._submit(update, context, reply.outline)
        else:
            await query.edit_message_text(INACTIVE)

    async def text(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Take a comparison reason, the current wizard answer or the free prompt."""
        message = update.effective_message
        if await self.review.reason(update, context):
            return
        if "wizard" in context.user_data:
            reply = wizard.answer(context.user_data["wizard"], message.text)
            await message.reply_text(reply.text, reply_markup=reply.keyboard)
        elif context.user_data.get("mode") == "free":
            prompt = message.text.strip()
            if not prompt or len(prompt) > BRIEF_LIMITS["plot"]:
                await message.reply_text(
                    f"Escribe una idea de hasta {BRIEF_LIMITS['plot']} caracteres."
                )
                return
            await self._submit(update, context, prompt)
        else:
            _, markup = next_step(self.queue, self.pairs, update.effective_user.id)
            await message.reply_text(WELCOME, reply_markup=markup)

    async def _choose(self, query, context, story_format: str, mode: str) -> None:
        """Start the chosen way: ask for the free idea or open the wizard."""
        if story_format not in METHODS or mode not in MODES:
            await query.edit_message_text(INACTIVE)
            return
        context.user_data.clear()
        context.user_data["format"] = story_format
        if mode == "free":
            context.user_data["mode"] = "free"
            await query.edit_message_text(
                f"{option_label(story_format, mode)}.\n\nEscribe tu idea en un mensaje "
                f"(máximo {BRIEF_LIMITS['plot']} caracteres). Puedes pedir el tono, la "
                "extensión («un cuento corto», «unas 3.000 palabras») o el idioma."
            )
            return
        context.user_data["wizard"], reply = wizard.start()
        await query.edit_message_text(
            f"{option_label(story_format, mode)}.\n\n{reply.text}", reply_markup=reply.keyboard
        )

    async def _same_idea(self, update: Update, context, job_id: int) -> None:
        """Ask for the participant's finished story again, with the other model."""
        job = self.queue.job(job_id)
        mine = job is not None and job["user_id"] == update.effective_user.id
        if not mine or job["status"] != "completed":
            await update.callback_query.edit_message_text(INACTIVE)
            return
        context.user_data.clear()
        context.user_data["format"] = other_format(job["story_format"])
        await update.callback_query.edit_message_text(
            f"La misma idea, ahora con el modelo {METHODS[context.user_data['format']]}."
        )
        await self._submit(update, context, job["request"], source_job=job_id)

    async def _submit(
        self, update: Update, context, request: str | StoryOutline, *, source_job=None
    ) -> None:
        """Queue the request and tell the participant where it stands."""
        story_format = context.user_data["format"]
        context.user_data.clear()
        try:
            job = self.queue.enqueue(
                update.effective_chat.id,
                update.effective_user.id,
                story_format,
                request,
                source_job=source_job,
            )
        except ValueError as exc:
            await context.bot.send_message(chat_id=update.effective_chat.id, text=str(exc))
            return
        ahead = self.queue.ahead(job)
        wait = f" Hay {ahead} antes que la tuya." if ahead else ""
        slow = " El Híbrido puede tardar media hora o más." if story_format == "simulated" else ""
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"Recibida.{wait} Te la envío cuando esté lista.{slow} /cancelar la detiene.",
        )
        self.worker.wake()
