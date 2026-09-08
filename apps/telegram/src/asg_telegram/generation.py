"""Queue-aware coordination of story generation and Telegram delivery."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from types import SimpleNamespace

from telegram.error import BadRequest, TelegramError

from .console import log_user_action
from .contract import (
    GenerationCancelled,
    GenerationEvent,
    GenerationFailure,
    GenerationProgress,
    StoryGeneratorAdapter,
    format_progress,
)
from .delivery import TelegramDelivery
from .queue import QueueRepository
from .states import ConversationState

LOGGER = logging.getLogger(__name__)
WARNING_MESSAGE_LIMIT = 3500
UNEXPECTED_ERROR_MESSAGE = (
    "No pude generar la historia por un error interno inesperado. "
    "Consulta el registro de la consola y vuelve a intentarlo. "
    "Código: UNEXPECTED_ERROR."
)


class GenerationCoordinator(TelegramDelivery):
    """Coordinate FIFO jobs, generation callbacks, delivery, and recovery."""

    PROGRESS_EDIT_TIMEOUT: float = 5.0
    MAX_RECOVERY_ATTEMPTS: int = 1

    def __init__(
        self, generator: StoryGeneratorAdapter, queue: QueueRepository | None = None
    ) -> None:
        """Configure the generator, optional queue, and concurrency limits."""
        self.generator = generator
        self.queue = queue
        self.active_users: set[int] = set()
        self.delivery_semaphore = asyncio.Semaphore(1)
        self.generation_semaphore = asyncio.Semaphore(1)

    async def restore_queue(self, application) -> None:
        """Resume waiting jobs and apply the recovery policy after a restart."""
        if not self.queue:
            return
        self.queue.recover_interrupted()
        await self._apply_recovery_policy(application)
        for job in self.queue.active():
            self.active_users.add(job.user_id)
            user = SimpleNamespace(id=job.user_id, username=job.username, full_name=job.username)
            context = SimpleNamespace(
                bot=application.bot,
                application=application,
                user_data=application.user_data[job.user_id],
            )
            application.create_task(
                self._generate_and_deliver(
                    context=context,
                    chat_id=job.chat_id,
                    user=user,
                    prompt=job.prompt,
                    progress_message_id=job.progress_message_id,
                    job_id=job.id,
                    narrative_profile=job.narrative_profile,
                )
            )
        await self._refresh_queue(application)

    async def _apply_recovery_policy(self, application) -> None:
        """Requeue each interrupted job once, then give up and say so.

        Without this every restart during a generation left the job parked in
        ``recovery_pending`` forever, because nothing moved it out again.
        """
        for job in self.queue.recovery_pending():
            if job.recovery_count <= self.MAX_RECOVERY_ATTEMPTS:
                self.queue.requeue(job.id)
                notice = (
                    "El bot se reinició durante tu historia. La volveré a generar "
                    "desde el principio y te avisaré cuando avance."
                )
            else:
                self.queue.finish(job.id, "failed", error_code="RECOVERY_EXHAUSTED")
                notice = (
                    "El bot se reinició varias veces durante tu historia y no pude "
                    "completarla. Usa /newstory para intentarlo otra vez. "
                    "Código: RECOVERY_EXHAUSTED."
                )
            try:
                await application.bot.send_message(chat_id=job.chat_id, text=notice)
            except TelegramError:
                LOGGER.warning("No se pudo avisar el trabajo interrumpido %s", job.id)

    async def _launch_generation(
        self, update, context, prompt: str, narrative_profile: str | None = None
    ) -> None:
        """Enqueue and schedule one user generation request."""
        user_id = update.effective_user.id
        if user_id in self.active_users:
            await update.effective_message.reply_text("Ya hay una generación activa para ti.")
            return
        self.active_users.add(user_id)
        log_user_action(
            LOGGER,
            user_id=user_id,
            username=update.effective_user.username or update.effective_user.full_name,
            action=f"Inició una generación {self.generator.display_name}",
            category="generación",
        )
        context.user_data.clear()
        context.user_data["state"] = ConversationState.GENERATING
        progress_message = await update.effective_message.reply_text(
            format_progress(
                GenerationProgress(
                    percent=0,
                    stage="starting",
                    description=f"Iniciando generación {self.generator.display_name}",
                )
            )
        )
        job_id = await self._enqueue(
            update, context, prompt, progress_message.message_id, narrative_profile
        )
        if self.queue and job_id is None:
            return
        context.application.create_task(
            self._generate_and_deliver(
                context=context,
                chat_id=update.effective_chat.id,
                user=update.effective_user,
                prompt=prompt,
                progress_message_id=progress_message.message_id,
                job_id=job_id,
                narrative_profile=narrative_profile,
            ),
            update=update,
        )

    async def _enqueue(
        self,
        update,
        context,
        prompt: str,
        progress_message_id: int,
        narrative_profile: str | None,
    ) -> str | None:
        """Persist a queue job, telling the user when one was already active."""
        if not self.queue:
            return None
        result = self.queue.enqueue(
            user_id=update.effective_user.id,
            username=update.effective_user.username or update.effective_user.full_name,
            chat_id=update.effective_chat.id,
            prompt=prompt,
            progress_message_id=progress_message_id,
            narrative_profile=narrative_profile,
        )
        if not result.created:
            context.user_data.clear()
            self.active_users.discard(update.effective_user.id)
            await update.effective_message.reply_text(
                "Ya tenías una solicitud en curso, así que no encolé esta. "
                "Usa /cancel si quieres reemplazarla."
            )
            return None
        await self._refresh_queue(context.application)
        return result.job.id

    async def _generate_and_deliver(
        self,
        *,
        context,
        chat_id: int,
        user,
        prompt: str,
        progress_message_id: int | None = None,
        job_id: str | None = None,
        narrative_profile: str | None = None,
    ) -> None:
        """Serialize generation while keeping progress reporting thread-safe."""
        loop = asyncio.get_running_loop()
        last_progress: list[GenerationProgress] = []

        def report_progress(update: GenerationProgress) -> None:
            """Forward synchronous pipeline progress to the Telegram event loop."""
            if job_id and self.queue and self.queue.cancellation_requested(job_id):
                raise GenerationCancelled(update.stage)
            last_progress[:] = [update]
            if progress_message_id is None:
                return
            try:
                future = asyncio.run_coroutine_threadsafe(
                    self._safe_edit_progress(
                        context,
                        chat_id,
                        progress_message_id,
                        format_progress(update),
                    ),
                    loop,
                )
                future.result(timeout=self.PROGRESS_EDIT_TIMEOUT)
            except Exception:
                LOGGER.warning("no se pudo confirmar la edición del progreso a tiempo")

        try:
            async with self.generation_semaphore:
                if job_id and self.queue:
                    if self.queue.position(job_id) is None:
                        await self._report_vanished_job(context, chat_id, progress_message_id)
                        return
                    self.queue.mark_running(job_id)
                    await self._refresh_queue(context.application)
                await self._run_generation_and_delivery(
                    context=context,
                    chat_id=chat_id,
                    user=user,
                    prompt=prompt,
                    progress_message_id=progress_message_id,
                    job_id=job_id,
                    narrative_profile=narrative_profile,
                    report_progress=report_progress,
                    last_progress=last_progress,
                )
        finally:
            self.active_users.discard(user.id)
            if self.queue:
                await self._refresh_queue(context.application)

    async def _report_vanished_job(self, context, chat_id, progress_message_id) -> None:
        """Close the progress message of a job cancelled before it started."""
        if progress_message_id is None:
            return
        await self._safe_edit_progress(
            context,
            chat_id,
            progress_message_id,
            "Solicitud cancelada antes de empezar. Usa /newstory cuando quieras.",
        )

    async def _run_generation_and_delivery(
        self,
        *,
        context,
        chat_id,
        user,
        prompt,
        progress_message_id,
        job_id,
        narrative_profile,
        report_progress,
        last_progress,
    ) -> None:
        """Generate, report metadata, deliver, and begin evaluation."""
        try:
            story_directory = await self._generate_story(
                prompt,
                user,
                job_id,
                narrative_profile,
                report_progress,
            )
        except Exception as exc:
            await self._handle_generation_failure(
                exc,
                context,
                chat_id,
                user,
                job_id,
                progress_message_id,
                last_progress,
            )
            return
        if job_id and self.queue:
            self.queue.set_run_dir(job_id, str(story_directory))
        self._log_generation_complete(user, story_directory)
        await self._report_run_metadata(
            context,
            chat_id,
            user,
            Path(story_directory),
            progress_message_id,
        )
        await self._deliver_completed_run(
            context,
            chat_id,
            user,
            Path(story_directory),
            job_id,
        )

    async def _generate_story(self, prompt, user, job_id, narrative_profile, report_progress):
        """Invoke the configured generator through the application contract."""

        def report_event(event: GenerationEvent) -> None:
            """Record structured pipeline events in the bot console."""
            log_user_action(
                LOGGER,
                user_id=user.id,
                username=user.username or user.full_name,
                action=event.message,
                category="generación",
            )

        def record_run(path: Path) -> None:
            """Persist the generated run directory for the bound queue job."""
            if job_id and self.queue:
                self.queue.set_run_dir(job_id, str(path))

        return await asyncio.to_thread(
            lambda: self.generator.generate(
                prompt,
                narrative_profile=narrative_profile,
                on_progress=report_progress,
                on_run_created=record_run if job_id and self.queue else None,
                on_event=report_event,
            )
        )

    async def _handle_generation_failure(
        self,
        error,
        context,
        chat_id,
        user,
        job_id,
        progress_message_id,
        last_progress,
    ) -> None:
        """Persist, display, and safely report a generation failure."""
        cancelled = isinstance(error, GenerationCancelled)
        recognized = isinstance(error, GenerationFailure)
        if job_id and self.queue:
            self.queue.finish(
                job_id,
                "cancelled" if cancelled else "failed",
                error_code=error.code if recognized else "UNEXPECTED_ERROR",
            )
        log_user_action(
            LOGGER,
            user_id=user.id,
            username=user.username or user.full_name,
            action="Cancelaste la generación"
            if cancelled
            else "Falló la generación de la historia",
            category="advertencia" if cancelled else "error",
            level=logging.WARNING if cancelled else logging.ERROR,
            exc_info=not cancelled,
        )
        if progress_message_id is not None:
            await self._safe_edit_progress(
                context,
                chat_id,
                progress_message_id,
                format_progress(self._failure_progress(error, recognized, last_progress)),
            )
        context.user_data.clear()
        message = error.public_message() if recognized else self._unexpected_message(job_id)
        await self._safe_notice(context, chat_id, message, user)

    @staticmethod
    def _failure_progress(error, recognized: bool, last_progress) -> GenerationProgress:
        """Describe where a generation stopped, even without any progress yet."""
        percent = last_progress[-1].percent if last_progress else 0
        if recognized:
            stage, summary = error.stage, error.summary
        else:
            stage = last_progress[-1].stage if last_progress else "antes de comenzar"
            summary = "Generación fallida"
        return GenerationProgress(
            percent=percent, stage="failed", description=f"{stage}: {summary}"[:180]
        )

    @staticmethod
    def _unexpected_message(job_id: str | None) -> str:
        """Report an internal defect, naming the job so logs can be matched."""
        if not job_id:
            return UNEXPECTED_ERROR_MESSAGE
        return f"{UNEXPECTED_ERROR_MESSAGE}\nSolicitud: {job_id}."

    @staticmethod
    def _log_generation_complete(user, story_directory) -> None:
        """Record the successful local completion of a generated story."""
        log_user_action(
            LOGGER,
            user_id=user.id,
            username=user.username or user.full_name,
            action=f"Generación terminada y guardada en {story_directory}",
            category="éxito",
        )

    async def _report_run_metadata(
        self,
        context,
        chat_id: int,
        user,
        story_directory: Path,
        progress_message_id: int | None,
    ) -> None:
        """Report final usage and quality warnings for a completed run."""
        summary = self.generator.summarize(story_directory)
        if progress_message_id is not None and summary.usage:
            await self._safe_edit_progress(
                context,
                chat_id,
                progress_message_id,
                f"[██████████] 100% — Historia terminada\n{summary.usage}",
            )
        if summary.warnings:
            await self._report_warnings(context, chat_id, user, summary.warnings)

    async def _report_warnings(self, context, chat_id: int, user, warnings) -> None:
        """Send one consolidated, actionable warning summary for a run."""
        message = (
            "La historia se completó, pero la revisión automática dejó "
            "estas advertencias:\n- " + "\n- ".join(warnings)
        )
        if len(message) > WARNING_MESSAGE_LIMIT:
            message = (
                message[: WARNING_MESSAGE_LIMIT - 60].rstrip()
                + "\n- Consulta revision_report.json para más detalles."
            )
        log_user_action(
            LOGGER,
            user_id=user.id,
            username=user.username or user.full_name,
            action="Historia completada con advertencias de calidad",
            category="advertencia",
            level=logging.WARNING,
        )
        await self._safe_notice(context, chat_id, message, user)

    async def _deliver_completed_run(
        self,
        context,
        chat_id: int,
        user,
        story_directory: Path,
        job_id: str | None,
    ) -> None:
        """Serialize story delivery and hand a success to evaluation handlers."""
        context.user_data["state"] = ConversationState.DELIVERING
        log_user_action(
            LOGGER,
            user_id=user.id,
            username=user.username or user.full_name,
            action="Esperando turno para entregar la historia",
            category="entrega",
        )
        try:
            async with self.delivery_semaphore:
                delivered = await self._deliver_story(
                    context=context,
                    chat_id=chat_id,
                    user=user,
                    story_path=story_directory / "story.md",
                )
                if not delivered:
                    context.user_data.clear()
                    await self._safe_notice(
                        context,
                        chat_id,
                        "La historia fue generada y permanece guardada, pero "
                        "Telegram no pudo recibir el archivo. Puedes comenzar "
                        "otra solicitud con /newstory.",
                        user,
                    )
                    return
                await self._begin_evaluation(context, chat_id, user, story_directory)
                if job_id and self.queue:
                    self.queue.finish(job_id, "completed")
        except Exception:
            log_user_action(
                LOGGER,
                user_id=user.id,
                username=user.username or user.full_name,
                action=(
                    "La historia fue generada, pero ocurrió un error "
                    "durante la entrega o el inicio de la evaluación"
                ),
                category="error",
                level=logging.ERROR,
                exc_info=True,
            )
            context.user_data.clear()
            await self._safe_notice(
                context,
                chat_id,
                "La historia fue generada y permanece guardada, pero "
                "la entrega no pudo completarse. Usa /newstory para continuar.",
                user,
            )
        finally:
            if job_id and self.queue:
                job = self.queue.get(job_id)
                if job and job.status == "running":
                    self.queue.finish(job_id, "failed", error_code="DELIVERY_FAILED")

    async def _begin_evaluation(self, context, chat_id: int, user, story_directory: Path) -> None:
        """Start evaluation after delivery; concrete handlers must implement it."""
        raise NotImplementedError

    async def _refresh_queue(self, application) -> None:
        """Refresh every queued user's position and estimated wait message."""
        if not self.queue:
            return
        jobs = self.queue.active()
        average = self.queue.average_duration()
        for position, job in enumerate(jobs, 1):
            text = self._queue_message(job.status, position, average)
            if job.progress_message_id:
                try:
                    await application.bot.edit_message_text(
                        chat_id=job.chat_id,
                        message_id=job.progress_message_id,
                        text=text,
                    )
                except TelegramError:
                    try:
                        message = await application.bot.send_message(chat_id=job.chat_id, text=text)
                        self.queue.set_progress_message(job.id, message.message_id)
                    except TelegramError:
                        pass

    @staticmethod
    def _queue_message(status: str, position: int, average: float | None) -> str:
        """Format a running or waiting queue status message."""
        if status == "running":
            return "Tu historia se está generando ahora. Posición 1."
        estimate = "estimación aún no disponible"
        if average:
            low = max(1, round((position - 1) * average * 0.8 / 60))
            high = max(low, round((position - 1) * average * 1.2 / 60))
            estimate = f"{low}–{high} minutos"
        return (
            f"Tu historia está en la posición {position}.\n"
            f"Tiempo estimado: {estimate}.\n"
            "Te avisaré automáticamente cuando avance."
        )

    async def _safe_edit_progress(
        self,
        context,
        chat_id: int,
        message_id: int,
        text: str,
    ) -> None:
        """Edit a progress message while ignoring harmless Telegram failures."""
        try:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=text,
            )
        except BadRequest as exc:
            if "message is not modified" not in str(exc).lower():
                LOGGER.warning("No se pudo actualizar el progreso: %s", exc)
        except TelegramError as exc:
            LOGGER.warning("No se pudo actualizar el progreso: %s", exc)
