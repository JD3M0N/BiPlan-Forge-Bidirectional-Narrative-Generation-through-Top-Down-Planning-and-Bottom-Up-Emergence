"""Queue-aware coordination of story generation and Telegram delivery."""

from __future__ import annotations

import asyncio
import inspect
import json
import logging
from pathlib import Path
from types import SimpleNamespace

from asg_top_down.errors import ASGError
from asg_top_down.progress import PipelineEvent, ProgressUpdate, format_progress
from telegram.error import BadRequest, TelegramError

from .console import log_user_action
from .delivery import TelegramDelivery
from .generators import StoryGenerator
from .queue import QueueRepository

LOGGER = logging.getLogger(__name__)


class GenerationCoordinator(TelegramDelivery):
    """Coordinate FIFO jobs, generation callbacks, delivery, and recovery."""

    def __init__(self, generator: StoryGenerator, queue: QueueRepository | None = None) -> None:
        """Configure the generator, optional queue, and concurrency limits."""
        self.generator = generator
        self.queue = queue
        self.active_users: set[int] = set()
        self.delivery_semaphore = asyncio.Semaphore(1)
        self.generation_semaphore = asyncio.Semaphore(1)

    async def restore_queue(self, application) -> None:
        """Restore waiting jobs and mark interrupted runs for manual recovery."""
        if not self.queue:
            return
        jobs = self.queue.recover_interrupted()
        for job in self.queue.recovery_pending():
            try:
                await application.bot.send_message(
                    chat_id=job.chat_id,
                    text=(
                        "El bot se reinició durante tu historia. El trabajo quedó marcado como "
                        "recovery_pending: sus checkpoints se conservan, pero la reanudación automática "
                        "todavía no está implementada. Las demás solicitudes continuarán."
                    ),
                )
            except TelegramError:
                LOGGER.warning("No se pudo avisar el trabajo pendiente %s", job.id)
        for job in jobs:
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
                )
            )
        await self._refresh_queue(application)

    async def _launch_generation(self, update, context, prompt: str) -> None:
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
        context.user_data["state"] = "generating"
        progress_message = await update.effective_message.reply_text(
            format_progress(
                ProgressUpdate(
                    percent=0,
                    stage="starting",
                    description=f"Iniciando generación {self.generator.display_name}",
                )
            )
        )
        job_id = self._enqueue(update, prompt, progress_message.message_id)
        if self.queue:
            await self._refresh_queue(context.application)
        context.application.create_task(
            self._generate_and_deliver(
                context=context,
                chat_id=update.effective_chat.id,
                user=update.effective_user,
                prompt=prompt,
                progress_message_id=progress_message.message_id,
                job_id=job_id,
            ),
            update=update,
        )

    def _enqueue(self, update, prompt: str, progress_message_id: int) -> str | None:
        """Persist a queue job when the coordinator has a repository."""
        if not self.queue:
            return None
        job = self.queue.enqueue(
            user_id=update.effective_user.id,
            username=update.effective_user.username or update.effective_user.full_name,
            chat_id=update.effective_chat.id,
            prompt=prompt,
            progress_message_id=progress_message_id,
        )
        return job.id

    async def _generate_and_deliver(
        self,
        *,
        context,
        chat_id: int,
        user,
        prompt: str,
        progress_message_id: int | None = None,
        job_id: str | None = None,
    ) -> None:
        """Serialize generation while keeping progress reporting thread-safe."""
        loop = asyncio.get_running_loop()
        last_progress: list[ProgressUpdate] = []

        def report_progress(update: ProgressUpdate) -> None:
            """Forward synchronous provider progress to the Telegram event loop."""
            last_progress[:] = [update]
            if progress_message_id is None:
                return
            future = asyncio.run_coroutine_threadsafe(
                self._safe_edit_progress(
                    context,
                    chat_id,
                    progress_message_id,
                    format_progress(update),
                ),
                loop,
            )
            future.result()

        try:
            async with self.generation_semaphore:
                if job_id and self.queue:
                    if self.queue.position(job_id) is None:
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
                    report_progress=report_progress,
                    last_progress=last_progress,
                )
        finally:
            self.active_users.discard(user.id)
            if self.queue:
                await self._refresh_queue(context.application)

    async def _run_generation_and_delivery(
        self,
        *,
        context,
        chat_id,
        user,
        prompt,
        progress_message_id,
        job_id,
        report_progress,
        last_progress,
    ) -> None:
        """Generate, report metadata, deliver, and begin evaluation."""
        try:
            story_directory = await self._generate_story(
                prompt,
                user,
                job_id,
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

    async def _generate_story(self, prompt, user, job_id, report_progress):
        """Invoke the configured generator with every callback it supports."""

        def report_event(event: PipelineEvent) -> None:
            """Record structured pipeline events in the bot console."""
            log_user_action(
                LOGGER,
                user_id=user.id,
                username=user.username or user.full_name,
                action=event.message,
                category="generación",
            )

        parameters = inspect.signature(self.generator.generate).parameters

        def record_run(path: Path) -> None:
            """Persist the generated run directory for the bound queue job."""
            assert self.queue is not None
            assert job_id is not None
            self.queue.set_run_dir(job_id, str(path))

        run_created = record_run if job_id and self.queue else None
        kwargs = {}
        if "on_progress" in parameters:
            kwargs["on_progress"] = report_progress
        if "on_run_created" in parameters:
            kwargs["on_run_created"] = run_created
        if "on_event" in parameters:
            kwargs["on_event"] = report_event
        return await asyncio.to_thread(self.generator.generate, prompt, **kwargs)

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
        if job_id and self.queue:
            self.queue.finish(
                job_id,
                "failed",
                error_code=getattr(error, "code", "UNEXPECTED_ERROR"),
            )
        log_user_action(
            LOGGER,
            user_id=user.id,
            username=user.username or user.full_name,
            action="Falló la generación de la historia",
            category="error",
            level=logging.ERROR,
            exc_info=True,
        )
        if progress_message_id is not None:
            percent = last_progress[-1].percent if last_progress else 0
            stage = getattr(error, "stage", last_progress[-1].stage if last_progress else "unknown")
            await self._safe_edit_progress(
                context,
                chat_id,
                progress_message_id,
                format_progress(
                    ProgressUpdate(
                        percent=percent,
                        stage="failed",
                        description=f"{stage}: {getattr(error, 'summary', 'Generación fallida')}"[
                            :180
                        ],
                    )
                ),
            )
        context.user_data.clear()
        message = (
            error.public_message()
            if isinstance(error, ASGError)
            else (
                "No pude generar la historia por un error interno inesperado. "
                "Consulta el registro de la consola y vuelve a intentarlo. "
                "Código: UNEXPECTED_ERROR."
            )
        )
        await self._safe_notice(context, chat_id, message, user)

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
        """Report final usage and quality warnings when artifacts are available."""
        usage_path = story_directory / "llm_usage_summary.json"
        if progress_message_id is not None and usage_path.is_file():
            try:
                usage = json.loads(usage_path.read_text(encoding="utf-8"))
                await self._safe_edit_progress(
                    context,
                    chat_id,
                    progress_message_id,
                    "[██████████] 100% — Historia terminada\n"
                    f"Gemini: {usage.get('calls', 0)} llamadas, "
                    f"{usage.get('total_tokens', 0)} tokens, "
                    f"{round(usage.get('total_wait_seconds', 0))}s esperando cuota.",
                )
            except (OSError, ValueError):
                pass
        await self._report_warnings(context, chat_id, user, story_directory)

    async def _report_warnings(self, context, chat_id: int, user, story_directory: Path) -> None:
        """Send one consolidated, actionable warning summary for a completed run."""
        metadata_path = story_directory / "metadata.json"
        if not metadata_path.is_file():
            return
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            warnings = metadata.get("warnings", [])
            if not warnings:
                return
            details = self._revision_warning_details(story_directory)
            writer_warning = any(
                str(warning).startswith("[WRITER_REVISION_REJECTED]") for warning in warnings
            )
            remaining = [
                str(warning)
                for warning in warnings
                if not (
                    details
                    and str(warning).startswith("[WRITER_REVISION_REJECTED]")
                )
            ]
            if details:
                remaining = details + remaining
            elif not writer_warning:
                remaining = [str(warning) for warning in warnings]
            message = (
                "La historia se completó, pero la revisión automática dejó "
                "estas advertencias:\n- "
                + "\n- ".join(remaining)
            )
            if len(message) > 3500:
                message = message[:3440].rstrip() + "\n- Consulta revision_report.json para más detalles."
            log_user_action(
                LOGGER,
                user_id=user.id,
                username=user.username or user.full_name,
                action="Historia completada con advertencias de calidad",
                category="advertencia",
                level=logging.WARNING,
            )
            await self._safe_notice(
                context,
                chat_id,
                message,
                user,
            )
        except (OSError, ValueError, TypeError):
            LOGGER.warning("No se pudieron leer las advertencias de la ejecución")

    @staticmethod
    def _revision_warning_details(story_directory: Path) -> list[str]:
        """Format structured Writer fallbacks and the final length impact."""
        report_path = story_directory / "revision_report.json"
        if not report_path.is_file():
            return []
        report = json.loads(report_path.read_text(encoding="utf-8"))
        details: list[str] = []
        for chapter in report.get("chapters", []):
            if chapter.get("warning_code") != "WRITER_REVISION_REJECTED":
                continue
            attempts = chapter.get("attempts", [])
            diagnostics = [
                attempt.get("diagnostic")
                for attempt in attempts
                if attempt.get("status") == "rejected" and attempt.get("diagnostic")
            ]
            if diagnostics and all(
                diagnostic.get("code") == "WORD_COUNT_OUT_OF_RANGE"
                for diagnostic in diagnostics
            ):
                counts = " y ".join(
                    str(diagnostic.get("actual_words", "?")) for diagnostic in diagnostics
                )
                latest = diagnostics[-1]
                details.append(
                    f"Capítulo {chapter.get('chapter_index')}: {len(diagnostics)} "
                    f"revisiones descartadas por longitud ({counts} palabras; rango válido "
                    f"{latest.get('minimum_words')}-{latest.get('maximum_words')}). "
                    f"Se entregó el borrador de {chapter.get('draft_words')} palabras. "
                    "Código: WRITER_REVISION_REJECTED."
                )
                continue
            failed = [
                attempt.get("exception_type", "error interno")
                for attempt in attempts
                if attempt.get("status") == "failed"
            ]
            reasons = [
                diagnostic.get("code", "RECHAZO_DESCONOCIDO")
                for diagnostic in diagnostics
            ] + failed
            details.append(
                f"Capítulo {chapter.get('chapter_index')}: no hubo una revisión válida "
                f"({', '.join(reasons) or 'sin diagnóstico'}). Se entregó el borrador de "
                f"{chapter.get('draft_words')} palabras. Código: WRITER_REVISION_REJECTED."
            )

        audit_path = story_directory / "length_audit.json"
        if details and audit_path.is_file():
            audit = json.loads(audit_path.read_text(encoding="utf-8"))
            total = audit.get("total", {})
            if total and not total.get("within_tolerance", True):
                details.append(
                    f"Longitud final: {total.get('actual_words')} palabras; mínimo esperado "
                    f"{total.get('minimum_words')} y objetivo {total.get('target_words')}."
                )
        return details

    async def _deliver_completed_run(
        self,
        context,
        chat_id: int,
        user,
        story_directory: Path,
        job_id: str | None,
    ) -> None:
        """Serialize story delivery and hand a success to evaluation handlers."""
        context.user_data["state"] = "delivering"
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
