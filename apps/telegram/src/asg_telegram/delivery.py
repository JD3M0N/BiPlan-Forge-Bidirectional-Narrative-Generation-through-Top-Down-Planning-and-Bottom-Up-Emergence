"""Reliable Telegram delivery for completed story files and fragments."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from telegram.constants import ParseMode
from telegram.error import BadRequest, NetworkError, TelegramError

from .console import log_user_action
from .prompts import telegram_story_chunks

LOGGER = logging.getLogger(__name__)
DOCUMENT_RETRY_DELAYS = (1, 2, 4)


class TelegramDelivery:
    """Deliver stories with retry and safe-notice behavior."""

    async def _deliver_story(self, *, context, chat_id: int, user, story_path: Path) -> bool:
        """Send the complete file first and then best-effort HTML fragments."""
        if not await self._send_document_with_retry(
            context=context,
            chat_id=chat_id,
            user=user,
            story_path=story_path,
        ):
            return False
        story = await asyncio.to_thread(story_path.read_text, encoding="utf-8")
        chunks = telegram_story_chunks(story)
        for index, chunk in enumerate(chunks, start=1):
            try:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=chunk,
                    parse_mode=ParseMode.HTML,
                )
            except TelegramError:
                log_user_action(
                    LOGGER,
                    user_id=user.id,
                    username=user.username or user.full_name,
                    action=(
                        f"Falló el fragmento {index}/{len(chunks)}; "
                        "se activó la entrega solo por archivo"
                    ),
                    category="advertencia",
                    level=logging.WARNING,
                    exc_info=True,
                )
                await self._safe_notice(
                    context,
                    chat_id,
                    "La historia fue generada correctamente. Telegram no pudo "
                    "mostrar todos los fragmentos, pero tienes el archivo completo.",
                    user,
                )
                break
        log_user_action(
            LOGGER,
            user_id=user.id,
            username=user.username or user.full_name,
            action="Historia entregada por Telegram",
            category="éxito",
        )
        return True

    async def _send_document_with_retry(
        self,
        *,
        context,
        chat_id: int,
        user,
        story_path: Path,
    ) -> bool:
        """Send a story document with bounded retries for network failures."""
        attempts = len(DOCUMENT_RETRY_DELAYS) + 1
        for attempt in range(1, attempts + 1):
            log_user_action(
                LOGGER,
                user_id=user.id,
                username=user.username or user.full_name,
                action=f"Enviando archivo, intento {attempt}/{attempts}",
                category="entrega",
            )
            try:
                with story_path.open("rb") as document:
                    await context.bot.send_document(
                        chat_id=chat_id,
                        document=document,
                        filename=story_path.name,
                        caption="Historia completa en formato Markdown.",
                    )
                return True
            except BadRequest:
                self._log_permanent_document_error(user)
                return False
            except NetworkError:
                if attempt == attempts:
                    self._log_exhausted_document_retries(user)
                    return False
                delay = DOCUMENT_RETRY_DELAYS[attempt - 1]
                log_user_action(
                    LOGGER,
                    user_id=user.id,
                    username=user.username or user.full_name,
                    action=f"Error temporal; nuevo intento en {delay} segundos",
                    category="advertencia",
                    level=logging.WARNING,
                    exc_info=True,
                )
                await asyncio.sleep(delay)
            except TelegramError:
                self._log_permanent_document_error(user)
                return False
        return False

    @staticmethod
    def _log_permanent_document_error(user) -> None:
        """Record a permanent Telegram rejection for a story document."""
        log_user_action(
            LOGGER,
            user_id=user.id,
            username=user.username or user.full_name,
            action="Telegram rechazó permanentemente el archivo",
            category="error",
            level=logging.ERROR,
            exc_info=True,
        )

    @staticmethod
    def _log_exhausted_document_retries(user) -> None:
        """Record that all temporary document retries were exhausted."""
        log_user_action(
            LOGGER,
            user_id=user.id,
            username=user.username or user.full_name,
            action="Se agotaron los reintentos del archivo",
            category="error",
            level=logging.ERROR,
            exc_info=True,
        )

    async def _safe_notice(self, context, chat_id: int, text: str, user) -> None:
        """Send a user notice without allowing Telegram errors to escape."""
        try:
            await context.bot.send_message(chat_id=chat_id, text=text)
        except TelegramError:
            log_user_action(
                LOGGER,
                user_id=user.id,
                username=user.username or user.full_name,
                action="No se pudo enviar el aviso al usuario",
                category="advertencia",
                level=logging.WARNING,
                exc_info=True,
            )
