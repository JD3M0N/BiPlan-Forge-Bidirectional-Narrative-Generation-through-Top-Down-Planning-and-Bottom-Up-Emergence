"""Reliable Telegram delivery for completed story files and fragments."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from asg_core import AudioGenerationError, create_story_audio
from telegram.constants import ParseMode
from telegram.error import BadRequest, NetworkError, TelegramError

from .console import log_user_action
from .prompts import telegram_story_chunks

LOGGER = logging.getLogger(__name__)
RETRY_DELAYS = (1, 2, 4)


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
        await self._deliver_audio(
            context=context,
            chat_id=chat_id,
            user=user,
            story_path=story_path,
            story=story,
        )
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

    async def _deliver_audio(
        self,
        *,
        context,
        chat_id: int,
        user,
        story_path: Path,
        story: str,
    ) -> bool:
        """Ensure and send narration without blocking the story workflow."""
        try:
            artifact = await create_story_audio(story_path)
        except AudioGenerationError:
            log_user_action(
                LOGGER,
                user_id=user.id,
                username=user.username or user.full_name,
                action="No se pudo crear el audio; la entrega de texto continuará",
                category="advertencia",
                level=logging.WARNING,
                exc_info=True,
            )
            await self._safe_notice(
                context,
                chat_id,
                "La historia está lista, pero no pude crear su audio. "
                "Continuaré con el texto y la evaluación.",
                user,
            )
            return False

        delivered = await self._send_audio_with_retry(
            context=context,
            chat_id=chat_id,
            user=user,
            audio_path=artifact.path,
            title=self._story_title(story),
            language=artifact.language,
            voice=artifact.voice,
        )
        if not delivered:
            await self._safe_notice(
                context,
                chat_id,
                "La historia y su audio permanecen guardados, pero Telegram no pudo "
                "recibir el MP3. Continuaré con el texto y la evaluación.",
                user,
            )
        return delivered

    async def _send_audio_with_retry(
        self,
        *,
        context,
        chat_id: int,
        user,
        audio_path: Path,
        title: str,
        language: str,
        voice: str,
    ) -> bool:
        """Send an MP3 with bounded retries for temporary network errors."""

        async def send() -> None:
            """Upload the narration file once."""
            with audio_path.open("rb") as audio:
                await context.bot.send_audio(
                    chat_id=chat_id,
                    audio=audio,
                    filename=audio_path.name,
                    title=title[:64],
                    performer="ASG",
                    caption=f"Narración {language} · {voice}",
                )

        return await self._send_with_retry(
            send,
            user=user,
            success="Audio entregado por Telegram",
            rejected="Telegram no pudo recibir el audio",
            exhausted="Telegram no pudo recibir el audio",
            failure_level=logging.WARNING,
        )

    @staticmethod
    def _story_title(story: str) -> str:
        """Extract a compact title from the first Markdown heading."""
        for line in story.splitlines():
            title = line.lstrip("#").strip() if line.lstrip().startswith("#") else ""
            if title:
                return title
        return "Historia narrada"

    async def _send_document_with_retry(
        self,
        *,
        context,
        chat_id: int,
        user,
        story_path: Path,
    ) -> bool:
        """Send a story document with bounded retries for network failures."""

        async def send() -> None:
            """Upload the story file once."""
            with story_path.open("rb") as document:
                await context.bot.send_document(
                    chat_id=chat_id,
                    document=document,
                    filename=story_path.name,
                    caption="Historia completa en formato Markdown.",
                )

        return await self._send_with_retry(
            send,
            user=user,
            attempt_label="Enviando archivo",
            rejected="Telegram rechazó permanentemente el archivo",
            exhausted="Se agotaron los reintentos del archivo",
        )

    async def _send_with_retry(
        self,
        send,
        *,
        user,
        rejected: str,
        exhausted: str,
        success: str | None = None,
        attempt_label: str | None = None,
        failure_level: int = logging.ERROR,
    ) -> bool:
        """Run one Telegram upload, retrying only temporary network errors.

        Permanent rejections are never retried: repeating a request Telegram
        already refused only delays telling the user that it failed. BadRequest
        must be caught before NetworkError because it subclasses it, so the
        order of these handlers is load-bearing.
        """
        attempts = len(RETRY_DELAYS) + 1
        for attempt in range(1, attempts + 1):
            if attempt_label:
                log_user_action(
                    LOGGER,
                    user_id=user.id,
                    username=user.username or user.full_name,
                    action=f"{attempt_label}, intento {attempt}/{attempts}",
                    category="entrega",
                )
            try:
                await send()
            except BadRequest:
                self._log_delivery_failure(user, rejected, failure_level)
                return False
            except NetworkError:
                if attempt == attempts:
                    self._log_delivery_failure(user, exhausted, failure_level)
                    return False
                delay = RETRY_DELAYS[attempt - 1]
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
                self._log_delivery_failure(user, rejected, failure_level)
                return False
            else:
                if success:
                    log_user_action(
                        LOGGER,
                        user_id=user.id,
                        username=user.username or user.full_name,
                        action=success,
                        category="éxito",
                    )
                return True
        return False

    @staticmethod
    def _log_delivery_failure(user, action: str, level: int) -> None:
        """Record why one Telegram upload will not be attempted again."""
        log_user_action(
            LOGGER,
            user_id=user.id,
            username=user.username or user.full_name,
            action=action,
            category="error" if level >= logging.ERROR else "advertencia",
            level=level,
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
