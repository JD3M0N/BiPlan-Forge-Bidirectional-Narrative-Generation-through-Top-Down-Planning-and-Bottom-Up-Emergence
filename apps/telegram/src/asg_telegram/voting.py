"""The /evaluar conversation: read two blind stories, then pick one for one criterion."""

from __future__ import annotations

import asyncio
from collections import defaultdict

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from .delivery import send_story

SIDES = {"L": ("left", "A"), "R": ("right", "B")}
CHOICES = {"A": "A", "B": "B", "X": "abstain"}
FINISHED = "¡Gracias! Ya respondiste todas tus comparaciones. Tus votos están guardados."


def _keyboard(rows: list[list[tuple[str, str]]]) -> InlineKeyboardMarkup:
    """Build an inline keyboard from (label, callback data) pairs."""
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(label, callback_data=data) for label, data in row] for row in rows]
    )


class Voting:
    """Drive one reader at a time through the study's blind pairwise questions."""

    def __init__(self, study) -> None:
        """Keep the study and one lock per reader, so double taps cannot race."""
        self.study = study
        self._locks: dict[int, asyncio.Lock] = defaultdict(asyncio.Lock)

    async def command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Start or resume the reader's comparisons."""
        user = update.effective_user
        async with self._locks[user.id]:
            await self._advance(context.bot, update.effective_chat.id, user.id)

    async def _advance(self, bot, chat_id: int, user_id: int) -> None:
        """Send whatever the reader needs next: unread stories or the question."""
        reader = self.study.participant(str(user_id))
        try:
            question = self.study.next_question(reader)
        except ValueError as exc:
            await bot.send_message(chat_id=chat_id, text=f"{exc} Prueba más tarde.")
            return
        if question is None:
            await bot.send_message(chat_id=chat_id, text=FINISHED)
            return
        unread = [key for key, (side, _) in SIDES.items() if not question[side]["read"]]
        if not unread:
            await self._ask(bot, chat_id, question)
            return
        if len(unread) == 2:
            await bot.send_message(
                chat_id=chat_id,
                text=f"Comparación {question['position']} de {question['total']}. "
                "Lee (o escucha) las dos historias y pulsa «Ya la leí» en cada una.",
            )
        for key in unread:
            side, label = SIDES[key]
            await send_story(
                bot,
                chat_id,
                question[side]["run_path"],
                name=f"Historia {label}",
                heading=f"Historia {label}",
                keyboard=_keyboard(
                    [
                        [("✅ Ya la leí", f"v:r:{question['id']}:{key}")],
                        [("Ya la conocía", f"v:k:{question['id']}:{key}")],
                    ]
                ),
            )

    async def _ask(self, bot, chat_id: int, question: dict) -> None:
        """Ask the criterion question with A, B and abstain buttons."""
        qid = question["id"]
        await bot.send_message(
            chat_id=chat_id,
            text=f"{question['question']}\n\n{question['guidance']}",
            reply_markup=_keyboard(
                [
                    [("Historia A", f"v:a:{qid}:A"), ("Historia B", f"v:a:{qid}:B")],
                    [("No puedo decidir", f"v:a:{qid}:X")],
                ]
            ),
        )

    async def callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle the reading, recognition and answer buttons."""
        query = update.callback_query
        _, action, qid, value = query.data.split(":")
        user = query.from_user
        async with self._locks[user.id]:
            reader = self.study.participant(str(user.id))
            try:
                if action == "a":
                    self.study.vote(reader, qid, CHOICES[value])
                    note = "Respuesta guardada."
                else:
                    question = self.study.next_question(reader)
                    if question is None or question["id"] != qid:
                        raise ValueError("Esta pregunta ya no está activa.")
                    story = question[SIDES[value][0]]["id"]
                    if action == "r":
                        self.study.mark_read(reader, qid, story)
                        note = "Leída."
                    else:
                        self.study.recognize(reader, qid, story)
                        note = "La cambiamos por otra."
            except ValueError as exc:
                await query.answer(str(exc), show_alert=True)
                return
            await query.answer(note)
            await query.edit_message_reply_markup(reply_markup=None)
            if action == "r":
                question = self.study.next_question(reader)
                if question and question["left"]["read"] and question["right"]["read"]:
                    await self._ask(context.bot, query.message.chat.id, question)
                return
            await self._advance(context.bot, query.message.chat.id, user.id)
