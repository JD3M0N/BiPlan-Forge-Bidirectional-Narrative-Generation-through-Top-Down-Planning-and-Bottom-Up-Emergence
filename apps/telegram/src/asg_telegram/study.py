"""Blind study conversations independent of disposable generation state."""

from __future__ import annotations

import asyncio
import html
import io
from collections import defaultdict

from asg_evaluation.catalog import guidance
from telegram import InlineKeyboardButton as Button
from telegram import InlineKeyboardMarkup as Keyboard
from telegram.constants import ParseMode

from .guide import CLOSED_TEXT, Step
from .prompts import telegram_story_chunks

PRIVATE_ONLY = "Participa desde un chat privado con el bot."
NOT_OPEN = (
    "La votación todavía no está abierta. Tu participación está guardada y te avisaré por "
    "aquí en cuanto empiece."
)
FINISHED = (
    "<b>Has completado todas tus comparaciones</b> ✅\n\n"
    "Muchas gracias: tus respuestas ya están guardadas. No tienes nada más pendiente."
)
PAUSED = (
    "Evaluación pausada. Todo lo que respondiste está guardado. Cuando quieras seguir, usa "
    "/evaluar y continuarás exactamente donde lo dejaste."
)
COLLECTION_CLOSED = (
    "La recogida de historias está cerrada, así que tu historia base ya no puede cambiarse."
)
CONTRIBUTE_NEW = (
    "Tu próxima historia será tu <b>historia base</b>: la que entra en la muestra del "
    "estudio. Elige narrativa o simulada y describe tu idea."
)
CONTRIBUTE_REPLACE = (
    "Vas a <b>reemplazar tu historia base</b>. La actual sigue inscrita hasta que la nueva "
    "termine correctamente; entonces la sustituirá. Elige narrativa o simulada y describe "
    "tu idea."
)
SESSION_BREAK = (
    "<b>Sesión {session} de {sessions}</b>\n\n"
    "Empiezas un grupo nuevo de relatos. Si lo necesitas, este es un buen momento para "
    "descansar: usa /pausa y vuelve con /evaluar cuando quieras."
)


class StudyConversation:
    """Store study progress in SQLite, never in generation's user_data."""

    def __init__(self, repository, generation) -> None:
        """Attach storage and the existing generation conversation."""
        self.repository = repository
        self.generation = generation
        self.locks = defaultdict(asyncio.Lock)

    @property
    def guide(self):
        """Return the participant guide, when the bot runs the full experiment."""
        return getattr(self.generation, "guide", None)

    async def evaluate(self, update, context) -> None:
        """Resume the first unanswered comparison, or explain why there is none."""
        if update.effective_chat.type != "private":
            await update.effective_message.reply_text(PRIVATE_ONLY)
            return
        user_id = update.effective_user.id
        status = self.guide.status(user_id)
        if status.step != Step.READY or status.participant is None:
            await self.guide.show(update, context)
            return
        if status.phase != "evaluation":
            if status.phase in {"collection", "frozen"}:
                await update.effective_message.reply_text(NOT_OPEN)
            else:
                await self.guide.show(update, context)
            return
        async with self.locks[user_id]:
            try:
                self.repository.pause(status.participant, False)
                await self._advance(context, update.effective_chat.id, status.participant)
            except ValueError as exc:
                await update.effective_message.reply_text(str(exc))

    async def contribute(self, update, context) -> None:
        """Reserve the next generation as the user's new or replacement base story."""
        if update.effective_chat.type != "private":
            await update.effective_message.reply_text(PRIVATE_ONLY)
            return
        status = self.guide.status(update.effective_user.id)
        if status.step in {Step.CONSENT, Step.PROFILE, Step.WAITING} or status.participant is None:
            await self.guide.show(update, context)
            return
        if status.phase != "collection":
            await update.effective_message.reply_text(COLLECTION_CLOSED)
            return
        try:
            if update.effective_user.id in self.generation.active_users:
                raise ValueError("Espera a que termine tu generación actual.")
            self.repository.request_contribution(status.participant)
        except ValueError as exc:
            await update.effective_message.reply_text(str(exc))
            return
        await update.effective_message.reply_text(
            CONTRIBUTE_REPLACE if status.enrolled else CONTRIBUTE_NEW, parse_mode=ParseMode.HTML
        )
        await self.generation.new_story(update, context)

    async def pause(self, update, context) -> None:
        """Persist a pause without cancelling generation or deleting votes."""
        status = self.guide.status(update.effective_user.id)
        if status.participant is None or status.phase != "evaluation":
            await update.effective_message.reply_text(NOT_OPEN)
            return
        self.repository.pause(status.participant)
        await update.effective_message.reply_text(PAUSED)

    async def callback(self, update, context) -> None:
        """Serialize a reader's buttons and validate them against durable assignments."""
        query = update.callback_query
        async with self.locks[update.effective_user.id]:
            try:
                parts = query.data.split(":")
                reader = self.repository.find_participant(str(update.effective_user.id))
                if reader is None:
                    raise ValueError("No estás inscrito en el estudio.")
                self._answer(reader["id"], parts)
                await query.answer()
                await query.edit_message_reply_markup(reply_markup=None)
                await self._advance(context, update.effective_chat.id, reader["id"])
            except (ValueError, IndexError) as exc:
                await query.answer(str(exc) or "Botón inválido.", show_alert=True)

    def _answer(self, participant: str, parts: list[str]) -> None:
        """Route a reading acknowledgement, known story or preference."""
        action, question, answer = parts[1:4]
        if action == "read":
            self.repository.mark_read(participant, question, answer)
        elif action == "known":
            self.repository.recognize(participant, question, answer)
        elif action == "vote":
            self.repository.vote(participant, question, answer)
        else:
            raise ValueError("Botón desconocido.")

    async def _advance(self, context, chat_id: int, participant: str) -> None:
        """Deliver unread stories before one high-level comparison question."""
        info = self.repository.info()
        if info["state"] != "evaluation":
            text = NOT_OPEN if info["state"] != "closed" else CLOSED_TEXT
            await context.bot.send_message(chat_id=chat_id, text=text, parse_mode=ParseMode.HTML)
            return
        q = self.repository.next_question(participant)
        if q is None:
            await context.bot.send_message(
                chat_id=chat_id, text=FINISHED, parse_mode=ParseMode.HTML
            )
            return
        progress = self.repository.progress(participant)
        unread = [side for side in ("left", "right") if not q[side]["read"]]
        if (
            len(unread) == 2
            and q["session"] > 1
            and not progress["answered_by_session"].get(q["session"])
        ):
            await context.bot.send_message(
                chat_id=chat_id,
                text=SESSION_BREAK.format(session=q["session"], sessions=progress["sessions"]),
                parse_mode=ParseMode.HTML,
            )
        if unread:
            await self._reading(context, chat_id, q, q[unread[0]])
            return
        snapshot = info["snapshot"]
        criterion = q["criterion"]
        hint = (snapshot.get("guidance") or guidance()).get(criterion, "")
        await context.bot.send_message(
            chat_id=chat_id,
            text=(
                f"<b>Pregunta {progress['answered'] + 1} de {progress['total']}</b> · "
                f"Sesión {q['session']} de {progress['sessions']}\n\n"
                f"<b>{html.escape(snapshot['catalog']['questions'][criterion])}</b>\n"
                f"<i>Qué mirar:</i> {html.escape(hint)}\n\n"
                f"A = {_label(q['left'])}\nB = {_label(q['right'])}\n\n"
                "Puedes volver a leer los relatos más arriba. Si necesitas parar, usa /pausa."
            ),
            parse_mode=ParseMode.HTML,
            reply_markup=Keyboard(
                [
                    [
                        Button(label, callback_data=f"study:vote:{q['id']}:{label}")
                        for label in ("A", "B")
                    ],
                    [Button("No puedo decidir", callback_data=f"study:vote:{q['id']}:abstain")],
                ]
            ),
        )

    @staticmethod
    async def _reading(context, chat_id: int, question: dict, story: dict) -> None:
        """Deliver complete prose with neutral labels and no metadata or audio."""
        label = _label(story)
        await context.bot.send_document(
            chat_id=chat_id,
            document=io.BytesIO(story["text"].encode("utf-8")),
            filename=f"{label}.txt",
            caption=f"Sesión {question['session']} · {label}",
        )
        for chunk in telegram_story_chunks(story["text"]):
            await context.bot.send_message(chat_id=chat_id, text=chunk, parse_mode="HTML")
        buttons = [("✅ Ya lo leí", "read"), ("Ya conocía esta historia", "known")]
        await context.bot.send_message(
            chat_id=chat_id,
            text=(
                f"<b>{label}</b>\n\n"
                "Lee el relato completo: lo tienes arriba como mensaje y como archivo. "
                "Cuando termines, pulsa «Ya lo leí».\n"
                "Si lo reconoces de antes, pulsa «Ya conocía esta historia» sin leerlo y te "
                "daré otro."
            ),
            parse_mode=ParseMode.HTML,
            reply_markup=Keyboard(
                [
                    [Button(text, callback_data=f"study:{action}:{question['id']}:{story['id']}")]
                    for text, action in buttons
                ]
            ),
        )


def _label(story: dict) -> str:
    """Name a story by an opaque fragment of its identifier."""
    return f"Relato {story['id'][1:7]}"
