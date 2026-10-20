"""The /evaluar conversation: the participant compares their own two stories, step by step.

1. The two stories arrive as Historia A and Historia B, without saying which model wrote each.
2. Once both are marked as read, three questions, one at a time: creativity, characters and
   plot, each with A, B or "No puedo decidir".
3. After each answer, an optional sentence saying why.
4. At the end the bot says which model was which and recommends the next step.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict

from telegram import Update
from telegram.ext import ContextTypes

from .delivery import send_story
from .generator import METHODS
from .guide import keyboard, next_step
from .pairs import criteria

INTRO = (
    "Vamos a comparar tus dos historias como pide el método de la tesis. No te pediré notas "
    "del 1 al 10, porque nadie sabe qué significa un 8: solo, de las dos, cuál prefieres en "
    "tres aspectos.\n\n"
    "Te llegan como Historia A e Historia B, sin decir con qué modelo se hizo cada una. "
    "Léelas (o escúchalas) enteras y pulsa «Ya la leí» en cada una. Después vienen las "
    "preguntas."
)
MISSING = (
    "Para comparar necesitas una historia terminada de cada modelo, Top-Down e Híbrido, que "
    "no hayas comparado ya."
)
REASON = "¿Por qué? Escríbelo en una frase, o pulsa «Saltar»."


class OwnReview:
    """Drive one participant at a time through the comparison of their own two stories."""

    def __init__(self, queue, pairs) -> None:
        """Keep the job queue, the pair store and one lock per participant."""
        self.queue = queue
        self.pairs = pairs
        self._locks: dict[int, asyncio.Lock] = defaultdict(asyncio.Lock)

    async def command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Start or resume the participant's comparison."""
        user = update.effective_user
        async with self._locks[user.id]:
            await self._advance(context.bot, update.effective_chat.id, user.id)

    async def callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle the read, answer and skip buttons of a comparison."""
        query = update.callback_query
        parts = query.data.split(":")
        user = query.from_user
        chat_id = query.message.chat.id
        async with self._locks[user.id]:
            if parts[1] == "go":
                await query.answer()
                await self._advance(context.bot, chat_id, user.id)
                return
            pair = self.pairs.pair(int(parts[2]))
            if pair is None or pair["user_id"] != user.id:
                await query.answer("Este botón ya no está activo.", show_alert=True)
                return
            try:
                note = self._apply(pair["id"], parts)
            except ValueError as exc:
                await query.answer(str(exc), show_alert=True)
                return
            await query.answer(note)
            await query.edit_message_reply_markup(reply_markup=None)
            pair = self.pairs.pair(pair["id"])
            if parts[1] == "r" and not pair["read"]:
                # The other story is already in the chat: wait for its button.
                return
            await self._advance(context.bot, chat_id, user.id, pair)

    async def reason(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
        """Take a typed reason when one is awaited; say whether the message was one."""
        user = update.effective_user
        async with self._locks[user.id]:
            pair = self.pairs.awaiting_reason(user.id)
            if pair is None:
                return False
            pair = self.pairs.give_reason(pair["id"], update.effective_message.text)
            await self._advance(context.bot, update.effective_chat.id, user.id, pair)
        return True

    def _apply(self, pair_id: int, parts: list[str]) -> str:
        """Record one button press and return the toast that acknowledges it."""
        action = parts[1]
        if action == "r":
            self.pairs.mark_read(pair_id, parts[3])
            return "Leída."
        if action == "a":
            self.pairs.answer(pair_id, parts[3], parts[4])
            return "Respuesta guardada."
        if action == "s":
            self.pairs.give_reason(pair_id, None)
            return "Seguimos."
        raise ValueError("Este botón ya no está activo.")

    async def _advance(self, bot, chat_id: int, user_id: int, pair: dict | None = None) -> None:
        """Send whatever the participant needs next in the given or their open comparison."""
        pair = pair or self.pairs.open_pair(user_id)
        if pair is None:
            found = self.pairs.candidate(user_id, self.queue.completed(user_id))
            if found is None:
                text, markup = next_step(self.queue, self.pairs, user_id)
                await bot.send_message(
                    chat_id=chat_id, text=f"{MISSING}\n\n{text}", reply_markup=markup
                )
                return
            pair = self.pairs.create(user_id, *found)
            await bot.send_message(chat_id=chat_id, text=INTRO)
            await self._send_unread(bot, chat_id, pair)
            return
        if pair["finished"]:
            await self._finish(bot, chat_id, pair)
        elif not pair["read"]:
            await self._send_unread(bot, chat_id, pair)
        elif pair["awaiting_reason"]:
            await bot.send_message(
                chat_id=chat_id,
                text=REASON,
                reply_markup=keyboard([[("Saltar", f"e:s:{pair['id']}")]]),
            )
        else:
            await self._ask(bot, chat_id, pair)

    async def _send_unread(self, bot, chat_id: int, pair: dict) -> None:
        """Send each story of the pair not yet marked as read, with its read button."""
        for side, read in (("A", pair["read_a"]), ("B", pair["read_b"])):
            if read:
                continue
            await send_story(
                bot,
                chat_id,
                pair["runs"][side],
                name=f"Historia {side}",
                heading=f"Historia {side}",
                keyboard=keyboard([[("✅ Ya la leí", f"e:r:{pair['id']}:{side}")]]),
            )

    async def _ask(self, bot, chat_id: int, pair: dict) -> None:
        """Ask the next of the three questions with A, B and abstain buttons."""
        listed = criteria()
        number = next(i for i, (key, _, _) in enumerate(listed, 1) if key == pair["next_criterion"])
        key, question, look = listed[number - 1]
        prefix = f"e:a:{pair['id']}:{key}"
        await bot.send_message(
            chat_id=chat_id,
            text=f"Pregunta {number} de {len(listed)}. {question}\n\nFíjate en: {look}",
            reply_markup=keyboard(
                [
                    [("Historia A", f"{prefix}:A"), ("Historia B", f"{prefix}:B")],
                    [("No puedo decidir", f"{prefix}:X")],
                ]
            ),
        )

    async def _finish(self, bot, chat_id: int, pair: dict) -> None:
        """Thank the participant, reveal which model was which and recommend what comes next."""
        reveal = (
            f"La Historia A era {METHODS[pair['formats']['A']]} y la B, "
            f"{METHODS[pair['formats']['B']]}."
        )
        text, markup = next_step(self.queue, self.pairs, pair["user_id"])
        await bot.send_message(
            chat_id=chat_id,
            text=f"¡Gracias! Tu comparación está guardada. {reveal}\n\n{text}",
            reply_markup=markup,
        )
