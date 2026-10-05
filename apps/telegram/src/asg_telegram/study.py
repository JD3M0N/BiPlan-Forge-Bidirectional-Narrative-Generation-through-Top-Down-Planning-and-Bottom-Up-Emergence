"""Blind study conversations independent of disposable generation state."""

from __future__ import annotations

import asyncio
import io
from collections import defaultdict

from telegram import InlineKeyboardButton as Button
from telegram import InlineKeyboardMarkup as Keyboard

from .prompts import telegram_story_chunks

PROFILES = {
    "occasional": "Lector ocasional",
    "regular": "Lector habitual",
    "expert": "Formación o trabajo en literatura",
}


class StudyConversation:
    """Store study progress in SQLite, never in generation's user_data."""

    def __init__(self, repository, generation) -> None:
        """Attach storage and the existing generation conversation."""
        self.repository = repository
        self.generation = generation
        self.locks = defaultdict(asyncio.Lock)

    async def evaluate(self, update, context) -> None:
        """Register a profile or resume the first unanswered comparison."""
        if update.effective_chat.type != "private":
            await update.effective_message.reply_text("Participa desde un chat privado.")
            return
        async with self.locks[update.effective_user.id]:
            try:
                reader = self.repository.participant(str(update.effective_user.id))
                if not reader["profile"]:
                    await update.effective_message.reply_text(
                        "Compararás relatos en creatividad, personajes y trama sin conocer su "
                        "método de generación. Puedes abstenerte y pausar. Tus votos se guardan "
                        "con un seudónimo para la tesis. Elige tu perfil para participar:",
                        reply_markup=Keyboard(
                            [
                                [Button(label, callback_data=f"study:profile:{key}")]
                                for key, label in PROFILES.items()
                            ]
                        ),
                    )
                    return
                self.repository.pause(reader["id"], False)
                await self._advance(context, update.effective_chat.id, reader["id"])
            except ValueError as exc:
                await update.effective_message.reply_text(str(exc))

    async def contribute(self, update, context) -> None:
        """Reserve the next generation as a replaceable contribution."""
        if update.effective_chat.type != "private":
            await update.effective_message.reply_text("Aporta desde un chat privado.")
            return
        try:
            if update.effective_user.id in self.generation.active_users:
                raise ValueError("Espera a que termine tu generación actual.")
            reader = self.repository.participant(str(update.effective_user.id))
            self.repository.request_contribution(reader["id"])
        except ValueError as exc:
            await update.effective_message.reply_text(str(exc))
            return
        await update.effective_message.reply_text(
            "Tu próxima historia completa en prosa será tu aportación. Elige narrativa o "
            "simulada y tus opciones. Puedes reemplazarla con /aportar antes del cierre. "
            "Registra también tu perfil lector con /evaluar."
        )
        await self.generation.new_story(update, context)

    async def pause(self, update, context) -> None:
        """Persist a pause without cancelling generation or deleting votes."""
        try:
            reader = self.repository.participant(str(update.effective_user.id))
            self.repository.pause(reader["id"])
            await update.effective_message.reply_text("Evaluación pausada. Continúa con /evaluar.")
        except ValueError as exc:
            await update.effective_message.reply_text(str(exc))

    async def callback(self, update, context) -> None:
        """Serialize a reader's buttons and validate them against durable assignments."""
        query = update.callback_query
        async with self.locks[update.effective_user.id]:
            try:
                parts = query.data.split(":")
                reader = self.repository.participant(str(update.effective_user.id))
                if parts[1] == "profile":
                    if parts[2] not in PROFILES:
                        raise ValueError("Perfil desconocido.")
                    reader = self.repository.participant(
                        str(update.effective_user.id), profile=parts[2]
                    )
                    self.repository.pause(reader["id"], False)
                else:
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
        state = info["state"]
        if state != "evaluation":
            text = "Tu participación está guardada. La votación todavía no está abierta."
            if state == "closed":
                text = "El estudio ha terminado. Gracias por participar."
            await context.bot.send_message(chat_id=chat_id, text=text)
            return
        q = self.repository.next_question(participant)
        if q is None:
            await context.bot.send_message(
                chat_id=chat_id, text="No tienes preguntas pendientes. Gracias."
            )
            return
        for side in ("left", "right"):
            if not q[side]["read"]:
                await self._reading(context, chat_id, q, q[side])
                return
        await context.bot.send_message(
            chat_id=chat_id,
            text=(
                f"Sesión {q['session']} · "
                f"{info['snapshot']['catalog']['questions'][q['criterion']]}\n"
                f"A: Relato {q['left']['id'][1:7]}\nB: Relato {q['right']['id'][1:7]}\n"
                "Puedes volver a los archivos anteriores o usar /pausa."
            ),
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
        label = f"Relato {story['id'][1:7]}"
        await context.bot.send_document(
            chat_id=chat_id,
            document=io.BytesIO(story["text"].encode("utf-8")),
            filename=f"{label}.txt",
            caption=f"Sesión {question['session']} · {label}",
        )
        for chunk in telegram_story_chunks(story["text"]):
            await context.bot.send_message(chat_id=chat_id, text=chunk, parse_mode="HTML")
        buttons = [("Ya lo leí", "read"), ("Ya conocía esta historia", "known")]
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"{label}: confirma cuando termines de leer.",
            reply_markup=Keyboard(
                [
                    [Button(text, callback_data=f"study:{action}:{question['id']}:{story['id']}")]
                    for text, action in buttons
                ]
            ),
        )
