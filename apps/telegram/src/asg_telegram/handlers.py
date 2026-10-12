"""Story creation: pick Top-Down or hybrid, then a free prompt or the guided wizard."""

from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from . import wizard
from .generator import BRIEF_LIMITS, METHODS, StoryOutline

WELCOME = (
    "Hola. Con este bot puedes crear historias y, cuando abra la votación, compararlas.\n\n"
    "/crear: nueva historia\n"
    "/evaluar: comparar historias\n"
    "/cancelar: cancelar lo que estés haciendo"
)


def _keyboard(rows: list[list[tuple[str, str]]]) -> InlineKeyboardMarkup:
    """Build an inline keyboard from (label, callback data) pairs."""
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(label, callback_data=data) for label, data in row] for row in rows]
    )


MENU = _keyboard([[("✍️ Crear historia", "c:new")], [("⚖️ Evaluar", "v:go:-:-")]])
METHOD_KEYBOARD = _keyboard([[(label, f"c:m:{fmt}")] for fmt, label in METHODS.items()])
MODE_KEYBOARD = _keyboard(
    [[("Libre: escribo una idea", "c:k:free")], [("Guiada: paso a paso", "c:k:guided")]]
)


class StoryBot:
    """Collect one story request per participant and hand it to the worker."""

    def __init__(self, queue, worker, voting) -> None:
        """Wire the conversation to the job queue, the worker and the voting flow."""
        self.queue = queue
        self.worker = worker
        self.voting = voting

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Greet the participant with the two things the bot does."""
        context.user_data.clear()
        await update.effective_message.reply_text(WELCOME, reply_markup=MENU)

    async def create(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Ask which approach writes the story."""
        context.user_data.clear()
        await update.effective_message.reply_text(
            "¿Cómo quieres que se escriba?\n\n"
            "Top-Down: se planifica la trama y luego se escribe.\n"
            "Híbrido: los personajes representan la obra y se narra lo que hicieron.",
            reply_markup=METHOD_KEYBOARD,
        )

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
        """Handle the menu, method, mode and wizard buttons."""
        query = update.callback_query
        data = query.data
        await query.answer()
        if data.startswith("v:go"):
            await self.voting.command(update, context)
        elif data == "c:new":
            await self.create(update, context)
        elif data.startswith("c:m:"):
            context.user_data.clear()
            context.user_data["format"] = data[4:]
            await query.edit_message_text(
                f"{METHODS[data[4:]]}. ¿Cómo quieres contarla?", reply_markup=MODE_KEYBOARD
            )
        elif data.startswith("c:k:") and "format" in context.user_data:
            if data == "c:k:free":
                context.user_data["mode"] = "free"
                await query.edit_message_text(
                    f"Escribe tu idea en un mensaje (máximo {BRIEF_LIMITS['plot']} caracteres)."
                )
            else:
                context.user_data["wizard"], reply = wizard.start()
                await query.edit_message_text(reply.text, reply_markup=reply.keyboard)
        elif data.startswith("w:") and "wizard" in context.user_data:
            reply = wizard.press(context.user_data["wizard"], data[2:])
            await query.edit_message_text(reply.text, reply_markup=reply.keyboard)
            if reply.outline is not None:
                await self._submit(update, context, reply.outline)
        else:
            await query.edit_message_text("Este botón ya no está activo. Empieza con /crear.")

    async def text(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Take the free prompt or the current wizard answer."""
        message = update.effective_message
        if "wizard" in context.user_data:
            reply = wizard.answer(context.user_data["wizard"], message.text)
            await message.reply_text(reply.text, reply_markup=reply.keyboard)
        elif context.user_data.get("mode") == "free":
            prompt = message.text.strip()
            if not prompt or len(prompt) > BRIEF_LIMITS["plot"]:
                await message.reply_text("Escribe una idea de hasta 4000 caracteres.")
                return
            await self._submit(update, context, prompt)
        else:
            await message.reply_text(WELCOME, reply_markup=MENU)

    async def _submit(self, update: Update, context, request: str | StoryOutline) -> None:
        """Queue the request and tell the participant where it stands."""
        story_format = context.user_data["format"]
        context.user_data.clear()
        try:
            job = self.queue.enqueue(
                update.effective_chat.id, update.effective_user.id, story_format, request
            )
        except ValueError as exc:
            await context.bot.send_message(chat_id=update.effective_chat.id, text=str(exc))
            return
        ahead = self.queue.ahead(job)
        wait = f" Hay {ahead} antes que la tuya." if ahead else ""
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"Recibida.{wait} Te la envío cuando esté lista (suele tardar varios minutos). "
            "/cancelar la detiene.",
        )
        self.worker.wake()
