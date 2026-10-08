"""Tell participants, once each, when the study opens collection, voting or closes."""

from __future__ import annotations

import asyncio
import logging

from telegram.error import BadRequest, Forbidden, TelegramError

from .guide import ANNOUNCEMENT_HEADERS, Step

LOGGER = logging.getLogger(__name__)
POLL_SECONDS = 60


class PhaseAnnouncer:
    """Poll the study phase and send each recipient its next step exactly once."""

    def __init__(self, guide) -> None:
        """Share the guide's storage and texts."""
        self.guide = guide

    def recipients(self, phase: str) -> list[int]:
        """List who must hear about a phase: base-story owners, then participants."""
        if phase == "collection":
            return [
                user_id
                for user_id in self.guide.queue.consented_ids()
                if self.guide.status(user_id).step == Step.BASE_STORY
            ]
        if phase in {"evaluation", "closed"}:
            return [
                int(external_id)
                for external_id in self.guide.repository.participant_ids()
                if external_id.isdigit() and self.guide.queue.access(int(external_id))
            ]
        return []

    async def announce(self, bot) -> int:
        """Send the current phase to every recipient not yet told, and count them."""
        phase = self.guide.repository.info()["state"]
        header = ANNOUNCEMENT_HEADERS.get(phase)
        if header is None:
            return 0
        sent = 0
        for user_id in self.recipients(phase):
            if self.guide.queue.announced(user_id, phase):
                continue
            try:
                await self.guide.send(bot, user_id, user_id, header=header)
            except (Forbidden, BadRequest) as exc:
                LOGGER.warning("No se pudo avisar al usuario %s: %s", user_id, exc)
                self.guide.queue.mark_announced(user_id, phase)
                continue
            except TelegramError as exc:
                LOGGER.warning("Aviso pendiente para el usuario %s: %s", user_id, exc)
                continue
            sent += 1
        if sent:
            LOGGER.info("Aviso de la fase %s enviado a %s participantes", phase, sent)
        return sent

    async def run(self, bot) -> None:
        """Announce forever until cancelled, surviving any single failed round."""
        while True:
            try:
                await self.announce(bot)
            except asyncio.CancelledError:
                raise
            except Exception:
                LOGGER.exception("Falló la revisión de la fase del estudio")
            await asyncio.sleep(POLL_SECONDS)
