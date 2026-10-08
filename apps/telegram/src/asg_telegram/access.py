"""Shared-key gate that keeps everyone outside the experiment away from the bot."""

from __future__ import annotations

import hmac
import logging
import math
from datetime import UTC, datetime, timedelta

from telegram.constants import ParseMode
from telegram.error import TelegramError
from telegram.ext import ApplicationHandlerStop

from .console import log_user_action
from .guide import (
    CALLBACK_LOCKED,
    KEY_ACCEPTED,
    KEY_LOCKED,
    KEY_REJECTED,
    LOCKED_TEXT,
    PRIVATE_ONLY,
)

LOGGER = logging.getLogger(__name__)
MAX_FAILURES = 5
LOCK_MINUTES = 15


class AccessGate:
    """Run before every handler and swallow updates from users without the key."""

    def __init__(self, queue, access_key: str, guide) -> None:
        """Keep the shared key, the access store and the guide that greets new users."""
        self.queue = queue
        self._key = access_key.encode("utf-8")
        self.guide = guide

    async def guard(self, update, context) -> None:
        """Let authorized users through; treat anything else as a key attempt."""
        user = update.effective_user
        if user is None:
            raise ApplicationHandlerStop
        if self.queue.access(user.id):
            return
        if update.callback_query is not None:
            await update.callback_query.answer(CALLBACK_LOCKED, show_alert=True)
            raise ApplicationHandlerStop
        message = update.effective_message
        if message is None:
            raise ApplicationHandlerStop
        if update.effective_chat.type != "private":
            await message.reply_text(PRIVATE_ONLY)
            raise ApplicationHandlerStop
        text = (message.text or "").strip()
        if not text or text.startswith("/"):
            await message.reply_text(LOCKED_TEXT, parse_mode=ParseMode.HTML)
            raise ApplicationHandlerStop
        await self._attempt(update, context, text)
        raise ApplicationHandlerStop

    async def _attempt(self, update, context, text: str) -> None:
        """Check one key attempt, honoring an active lockout first."""
        user = update.effective_user
        message = update.effective_message
        locked = self.queue.locked_until(user.id)
        if locked:
            minutes = math.ceil((locked - datetime.now(UTC)).total_seconds() / 60)
            await message.reply_text(KEY_LOCKED.format(minutes=max(1, minutes)))
            return
        if hmac.compare_digest(text.encode("utf-8"), self._key):
            self.queue.grant(user.id)
            self._log(user, "entró con la clave de acceso", "éxito")
            try:
                await message.delete()
            except TelegramError:
                LOGGER.debug("No se pudo borrar el mensaje con la clave")
            await message.reply_text(KEY_ACCEPTED)
            await self.guide.show(update, context)
            return
        remaining = self.queue.record_failure(
            user.id, limit=MAX_FAILURES, lock=timedelta(minutes=LOCK_MINUTES)
        )
        self._log(user, "escribió una clave incorrecta", "advertencia")
        if remaining:
            await message.reply_text(KEY_REJECTED.format(remaining=remaining))
        else:
            await message.reply_text(KEY_LOCKED.format(minutes=LOCK_MINUTES))

    @staticmethod
    def _log(user, action: str, category: str) -> None:
        """Record an access event without ever writing what the user typed."""
        log_user_action(
            LOGGER,
            user_id=user.id,
            username=user.username or user.full_name,
            action=action,
            category=category,
        )
