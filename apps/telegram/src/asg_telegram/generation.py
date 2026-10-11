"""Queue-aware coordination of story generation and Telegram delivery."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Mapping
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

from asg_core import format_progress
from telegram.error import BadRequest, TelegramError

from .console import log_user_action
from .contract import (
    GenerationAvailability,
    GenerationCancelled,
    GenerationEvent,
    GenerationFailure,
    GenerationProgress,
    OptionValue,
    StoryGeneratorAdapter,
    StoryOutline,
)
from .delivery import DEFAULT_DOCUMENT_CAPTION, TelegramDelivery
from .guide import BASE_RETRY
from .queue import QueueRepository
from .states import ConversationState

LOGGER = logging.getLogger(__name__)
WARNING_MESSAGE_LIMIT = 3500
AUTHOR_PRIORITY = 1
BLIND_PROGRESS = "Generando tu historia"
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
        self._memory_options: dict[int, dict[str, OptionValue]] = {}
        self.study = None
        self.guide = None
        self.author_chat_id: int | None = None
        self.gate = None
        self._job_tasks: set[asyncio.Task] = set()
        self._stopping = False

    def schedule(self, application, coroutine, *, update=None):
        """Let embedding applications manage generation tasks by default."""
        if update is None:
            return application.create_task(coroutine)
        return application.create_task(coroutine, update=update)

    def background_task(self, application, coroutine, *, update=None):
        """Own long quota waits outside Telegram's update-task shutdown barrier."""
        task = asyncio.create_task(coroutine)
        self._job_tasks.add(task)
        task.add_done_callback(self._task_done)
        return task

    def _task_done(self, task) -> None:
        """Release task references and consume unexpected background failures."""
        self._job_tasks.discard(task)
        if not task.cancelled() and task.exception():
            LOGGER.error("Generation task failed", exc_info=task.exception())

    async def stop_generation_tasks(self) -> None:
        """Interrupt waiting tasks while leaving durable jobs recoverable on restart."""
        self._stopping = True
        tasks = list(self._job_tasks)
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    # --- per-user option preferences ------------------------------------

    def stored_options(self, user_id: int) -> dict[str, OptionValue]:
        """Return a user's saved option overrides, without merging defaults."""
        if self.queue:
            return self.queue.user_options(user_id)
        return dict(self._memory_options.get(user_id, {}))

    def _save_stored_options(self, user_id: int, options: Mapping[str, OptionValue]) -> None:
        """Persist a user's option overrides, in the queue when one exists."""
        if self.queue:
            self.queue.save_user_options(user_id, options)
        else:
            self._memory_options[user_id] = dict(options)

    def effective_options(self, user_id: int) -> tuple[dict[str, OptionValue], bool]:
        """Return a user's normalized options, resetting them if they no longer validate.

        The second value is True exactly when stored preferences had to be
        discarded, so the caller can tell the user why their choices changed.
        """
        stored = self.stored_options(user_id)
        try:
            return self.generator.normalize_options(stored), False
        except ValueError:
            self._save_stored_options(user_id, {})
            return self.generator.normalize_options({}), True

    def change_option(self, user_id: int, key: str, value: OptionValue) -> dict[str, OptionValue]:
        """Set one option for a user, validating the whole result before saving it."""
        stored = self.stored_options(user_id)
        stored[key] = value
        normalized = self.generator.normalize_options(stored)
        self._save_stored_options(user_id, stored)
        return normalized

    def reset_options(self, user_id: int) -> None:
        """Forget a user's option overrides, returning them to the defaults."""
        self._save_stored_options(user_id, {})

    # --- recovery ---------------------------------------------------------

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
            request: str | StoryOutline = (
                StoryOutline.from_dict(job.brief) if job.brief else job.prompt
            )
            options = job.options if job.options is not None else self._legacy_options(job)
            self.schedule(
                application,
                self._generate_and_deliver(
                    context=context,
                    chat_id=job.chat_id,
                    user=user,
                    prompt=request,
                    options=options,
                    progress_message_id=job.progress_message_id,
                    job_id=job.id,
                ),
            )
        await self.ensure_author_jobs(application)
        await self._refresh_queue(application)

    @staticmethod
    def _legacy_options(job) -> dict[str, OptionValue]:
        """Rebuild an options snapshot from a pre-7.3 job's plain columns."""
        options: dict[str, OptionValue] = {}
        if job.story_format:
            options["format"] = job.story_format
        if job.narrative_profile:
            options["narrative_profile"] = job.narrative_profile
        return options

    async def _apply_recovery_policy(self, application) -> None:
        """Requeue each interrupted job once, then give up and say so.

        Without this every restart during a generation left the job parked in
        ``recovery_pending`` forever, because nothing moved it out again.
        """
        for job in self.queue.recovery_pending():
            if job.run_dir and self._completed_run(Path(job.run_dir)):
                self.queue.requeue(job.id)
                continue
            if job.recovery_count <= self.MAX_RECOVERY_ATTEMPTS:
                self.queue.requeue(job.id)
                notice = (
                    "El bot se reinició durante tu historia. La volveré a generar "
                    "desde el principio y te avisaré cuando avance."
                )
            else:
                self.queue.finish(job.id, "failed", error_code="RECOVERY_EXHAUSTED")
                if self.study:
                    self.study.repository.release_contribution(str(job.user_id), job.id)
                notice = (
                    "El bot se reinició varias veces durante tu historia y no pude "
                    "completarla. Usa /newstory para intentarlo otra vez. "
                    "Código: RECOVERY_EXHAUSTED."
                )
            try:
                await application.bot.send_message(chat_id=job.chat_id, text=notice)
            except TelegramError:
                LOGGER.warning("No se pudo avisar el trabajo interrumpido %s", job.id)

    # --- launching a job ---------------------------------------------------

    async def _launch_generation(
        self,
        update,
        context,
        request: str | StoryOutline,
    ) -> None:
        """Enqueue and schedule one user generation request."""
        user_id = update.effective_user.id
        if user_id in self.active_users:
            await update.effective_message.reply_text("Ya hay una generación activa para ti.")
            return
        self.active_users.add(user_id)
        if context.user_data.get("pack_participant"):
            status = self.guide.status(user_id)
            fmt = self.study.repository.assign_format(status.participant)
            options, was_reset = self.generator.normalize_options({"format": fmt}), False
        else:
            options, was_reset = self.effective_options(user_id)
        if was_reset:
            await update.effective_message.reply_text(
                "Tus opciones guardadas ya no eran válidas y las restablecí a las de por defecto."
            )
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
        job_id = await self._enqueue(update, context, request, progress_message.message_id, options)
        if self.queue and job_id is None:
            return
        self.schedule(
            context.application,
            self._generate_and_deliver(
                context=context,
                chat_id=update.effective_chat.id,
                user=update.effective_user,
                prompt=request,
                options=options,
                progress_message_id=progress_message.message_id,
                job_id=job_id,
            ),
            update=update,
        )

    async def _enqueue(
        self,
        update,
        context,
        request: str | StoryOutline,
        progress_message_id: int,
        options: Mapping[str, OptionValue],
    ) -> str | None:
        """Persist a queue job, telling the user when one was already active."""
        if not self.queue:
            return None
        brief = request.to_dict() if isinstance(request, StoryOutline) else None
        prompt_text = request if isinstance(request, str) else request.plot
        profile = options.get("narrative_profile")
        result = self.queue.enqueue(
            user_id=update.effective_user.id,
            username=update.effective_user.username or update.effective_user.full_name,
            chat_id=update.effective_chat.id,
            prompt=prompt_text,
            progress_message_id=progress_message_id,
            narrative_profile=str(profile) if profile else None,
            story_format=str(options.get("format")) if options.get("format") else None,
            options=dict(options),
            brief=brief,
            priority=self._generation_priority(update.effective_user.id),
        )
        if not result.created:
            context.user_data.clear()
            self.active_users.discard(update.effective_user.id)
            await update.effective_message.reply_text(
                "Ya tenías una solicitud en curso, así que no encolé esta. "
                "Usa /cancel si quieres reemplazarla."
            )
            return None
        if self.study:
            self.study.repository.bind_contribution(str(update.effective_user.id), result.job.id)
        await self._refresh_queue(context.application)
        return result.job.id

    def _generation_priority(self, user_id: int) -> int:
        """Favor first contributions, then replacements or researcher stories, then the rest.

        Once a pack is complete, late contributions no longer fill it and wait like free use.
        """
        if user_id < 0:
            return AUTHOR_PRIORITY
        if self.guide:
            status = self.guide.status(user_id)
            if status.contributing:
                if status.pack and self.study.repository.pack_complete():
                    return 2
                return 1 if status.enrolled else 0
        return 2

    def _availability(self, options) -> GenerationAvailability:
        """Support older adapters that do not expose capacity diagnostics."""
        query = getattr(self.generator, "availability", None)
        return query(options or {}) if query else GenerationAvailability()

    async def _wait_for_turn(self, job_id, options, application) -> bool:
        """Wait outside the generation lock so deferred jobs do not block eligible work."""
        if not self.queue or not job_id:
            return True
        while True:
            job = self.queue.get(job_id)
            if not job or job.status not in {"queued", "running", "quota_wait"}:
                return False
            if self.queue.next_ready() == job_id:
                capacity = await asyncio.to_thread(self._availability, options)
                if capacity.available:
                    return True
                until = capacity.retry_at or (datetime.now(UTC) + timedelta(minutes=5)).isoformat()
                self.queue.defer(job_id, until, capacity.reason)
                await self._refresh_queue(application)
            await asyncio.sleep(1)

    # --- running a job -------------------------------------------------------

    async def _generate_and_deliver(
        self,
        *,
        context,
        chat_id: int,
        user,
        prompt: str | StoryOutline,
        options: Mapping[str, OptionValue] | None = None,
        progress_message_id: int | None = None,
        job_id: str | None = None,
    ) -> None:
        """Serialize generation while keeping progress reporting thread-safe."""
        loop = asyncio.get_running_loop()
        last_progress: list[GenerationProgress] = []
        blind = self._blind(user.id, job_id)

        def report_progress(update: GenerationProgress) -> None:
            """Forward synchronous pipeline progress to the Telegram event loop."""
            if blind:
                update = GenerationProgress(update.percent, "generating", BLIND_PROGRESS)
            changed = not last_progress or (
                last_progress[-1].percent,
                last_progress[-1].stage,
                last_progress[-1].description,
            ) != (update.percent, update.stage, update.description)
            last_progress[:] = [update]
            if changed:
                log_user_action(
                    LOGGER,
                    user_id=user.id,
                    username=user.username or user.full_name,
                    action=f"{update.percent}% · {update.description}",
                    category="progreso",
                )
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

        should_cancel = (
            (lambda: self._stopping or self.queue.cancellation_requested(job_id))
            if job_id and self.queue
            else None
        )

        try:
            while await self._wait_for_turn(job_id, options, getattr(context, "application", None)):
                async with self.generation_semaphore:
                    if job_id and self.queue:
                        if self.queue.next_ready() != job_id:
                            continue
                        self.queue.mark_running(job_id)
                        await self._refresh_queue(context.application, include_running=True)
                    await self._run_generation_and_delivery(
                        context=context,
                        chat_id=chat_id,
                        user=user,
                        prompt=prompt,
                        options=options or {},
                        progress_message_id=progress_message_id,
                        job_id=job_id,
                        report_progress=report_progress,
                        should_cancel=should_cancel,
                        last_progress=last_progress,
                    )
                job = self.queue.get(job_id) if self.queue and job_id else None
                if not job or job.status != "quota_wait":
                    break
            else:
                await self._report_vanished_job(context, chat_id, progress_message_id)
        finally:
            other_active = self.queue and any(
                job.user_id == user.id and job.id != job_id for job in self.queue.active()
            )
            if not other_active:
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
        options,
        progress_message_id,
        job_id,
        report_progress,
        should_cancel,
        last_progress,
    ) -> None:
        """Generate, report metadata, deliver, and begin evaluation."""
        try:
            existing = self.queue.get(job_id) if self.queue and job_id else None
            directory = Path(existing.run_dir) if existing and existing.run_dir else None
            if directory and self._completed_run(directory):
                story_directory = directory
            else:
                story_directory = await self._generate_story(
                    prompt,
                    options,
                    user,
                    job_id,
                    report_progress,
                    should_cancel,
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
        enrolled = False
        if self.study:
            enrolled = await self._record_study_generation(
                context, chat_id, user, job_id, Path(story_directory)
            )
        self._log_generation_complete(user, story_directory)
        summary = self.generator.summarize(Path(story_directory))
        if self._blind(user.id, job_id):
            # Captions, call counts and warnings would tell a pack reader the method.
            summary = replace(summary, usage=None, warnings=(), document_caption=None)
        await self._report_run_metadata(
            context,
            chat_id,
            user,
            progress_message_id,
            summary,
        )
        await self._deliver_completed_run(
            context,
            chat_id,
            user,
            Path(story_directory),
            job_id,
            summary,
            enrolled=enrolled,
        )

    @staticmethod
    def _completed_run(directory: Path) -> bool:
        """Recognize a finished persisted run after interrupted delivery."""
        import json

        try:
            metadata = json.loads((directory / "metadata.json").read_text(encoding="utf-8"))
            return metadata.get("status") == "completed" and (directory / "story.md").is_file()
        except (OSError, ValueError):
            return False

    def _blind(self, user_id: int, job_id: str | None) -> bool:
        """Tell whether the study assigned this job's format and must keep it hidden."""
        if not (self.study and job_id) or user_id < 0:
            return False
        return self.study.repository.assigned_format(str(user_id), job_id) is not None

    async def ensure_author_jobs(self, application) -> None:
        """Queue each pending researcher story of a pack study as a durable job."""
        repository = self.study.repository if self.study else None
        if not (self.queue and repository and self.author_chat_id):
            return
        if repository.info()["mode"] != "pack":
            return
        for request in repository.pending_author_requests():
            job = self.queue.get(request["job_id"]) if request["job_id"] else None
            if job and job.status in {"queued", "running", "quota_wait", "recovery_pending"}:
                continue
            user = SimpleNamespace(
                id=-request["slot"],
                username=f"autor-{request['slot']}",
                full_name=f"autor-{request['slot']}",
            )
            options = self.generator.normalize_options({"format": request["format"]})
            result = self.queue.enqueue(
                user_id=user.id,
                username=user.username,
                chat_id=self.author_chat_id,
                prompt=request["prompt"],
                story_format=request["format"],
                options=dict(options),
                priority=AUTHOR_PRIORITY,
            )
            if not result.created:
                continue
            repository.bind_author_job(request["slot"], result.job.id)
            self.active_users.add(user.id)
            context = SimpleNamespace(
                bot=application.bot,
                application=application,
                user_data=application.user_data[user.id],
            )
            self.schedule(
                application,
                self._generate_and_deliver(
                    context=context,
                    chat_id=self.author_chat_id,
                    user=user,
                    prompt=request["prompt"],
                    options=options,
                    job_id=result.job.id,
                ),
            )

    async def _record_study_generation(self, context, chat_id, user, job_id, directory) -> bool:
        """Record exposure and enroll a reserved base story, keeping failures retryable."""
        repository = self.study.repository
        if user.id < 0:
            try:
                return await asyncio.to_thread(
                    repository.complete_author_generation, job_id, directory
                )
            except (ValueError, OSError) as exc:
                LOGGER.warning("No se inscribió la historia del autor %s: %s", job_id, exc)
                return False
        try:
            return await asyncio.to_thread(
                repository.complete_generation, str(user.id), job_id, directory
            )
        except (ValueError, OSError) as exc:
            LOGGER.warning("No se inscribió la historia base de %s: %s", user.id, exc)
            if job_id:
                repository.release_contribution(str(user.id), job_id)
            await self._safe_notice(
                context,
                chat_id,
                f"La historia se generó, pero no pude inscribirla como tu historia base: {exc}\n"
                "Te la entrego igualmente. Para aportar otra, usa /aportar.",
                user,
            )
            return False

    async def _generate_story(self, prompt, options, user, job_id, report_progress, should_cancel):
        """Invoke the configured generator through the application contract."""

        def report_event(event: GenerationEvent) -> None:
            """Record structured pipeline events in the bot console."""
            level = logging.DEBUG if (event.kind or "").startswith("artifact_") else logging.INFO
            log_user_action(
                LOGGER,
                user_id=user.id,
                username=user.username or user.full_name,
                action=event.message,
                category="generación",
                level=level,
            )

        def record_run(path: Path) -> None:
            """Persist the generated run directory for the bound queue job."""
            if job_id and self.queue:
                self.queue.set_run_dir(job_id, str(path))

        return await asyncio.to_thread(
            lambda: self.generator.generate(
                prompt,
                options=options,
                on_progress=report_progress,
                on_run_created=record_run if job_id and self.queue else None,
                on_event=report_event,
                should_cancel=should_cancel,
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
        if (
            isinstance(error, GenerationFailure)
            and error.retryable_quota
            and self.queue
            and job_id
            and not self.queue.cancellation_requested(job_id)
        ):
            job = self.queue.get(job_id)
            capacity = self._availability(job.options if job else {})
            until = capacity.retry_at or (datetime.now(UTC) + timedelta(minutes=5)).isoformat()
            self.queue.defer(job_id, until, "Cuota agotada; tu idea sigue guardada")
            await self._safe_notice(
                context,
                chat_id,
                "La cuota del proveedor se agotó. Tu solicitud conserva su turno. "
                "Volveré a generar la historia automáticamente cuando haya capacidad.",
                user,
            )
            return
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
        if self.study and job_id:
            self.study.repository.release_contribution(str(user.id), job_id)
        if self.guide and self.guide.status(user.id).contributing:
            message = f"{message}\n\n{BASE_RETRY}"
        await self._safe_notice(context, chat_id, message, user)
        if user.id < 0 and not cancelled and not self._stopping:
            await self.ensure_author_jobs(context.application)

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
        progress_message_id: int | None,
        summary,
    ) -> None:
        """Report final usage and quality warnings for a completed run."""
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
        summary,
        *,
        enrolled: bool = False,
    ) -> None:
        """Serialize story delivery, then tell the user what comes next."""
        context.user_data["state"] = ConversationState.DELIVERING
        log_user_action(
            LOGGER,
            user_id=user.id,
            username=user.username or user.full_name,
            action="Esperando turno para entregar la historia",
            category="entrega",
        )
        caption = summary.document_caption or DEFAULT_DOCUMENT_CAPTION
        try:
            async with self.delivery_semaphore:
                delivered = await self._deliver_story(
                    context=context,
                    chat_id=chat_id,
                    user=user,
                    story_path=story_directory / "story.md",
                    caption=caption,
                    audio=summary.audio,
                    audio_voice=summary.audio_voice,
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
                if job_id and self.queue:
                    self.queue.finish(job_id, "completed")
                await self._after_delivery(context, chat_id, user, enrolled)
        except Exception:
            log_user_action(
                LOGGER,
                user_id=user.id,
                username=user.username or user.full_name,
                action=("La historia fue generada, pero ocurrió un error durante la entrega"),
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
                if job and job.status == "running" and not self._stopping:
                    self.queue.finish(job_id, "failed", error_code="DELIVERY_FAILED")

    async def _after_delivery(self, context, chat_id: int, user, enrolled: bool) -> None:
        """Guide the user after delivery; concrete handlers must implement it."""
        raise NotImplementedError

    async def _refresh_queue(self, application, *, include_running: bool = False) -> None:
        """Refresh every queued user's position and estimated wait message.

        The running job owns the same message id as its live progress bar, so refreshing it
        from anywhere but the queued-to-running transition replaces that bar with a static
        queue notice. It still counts for the positions the waiting users are told.
        """
        if not self.queue:
            return
        jobs = self.queue.active()
        average = self.queue.average_duration()
        for position, job in enumerate(jobs, 1):
            if job.status == "running" and not include_running:
                continue
            text = self._queue_message(job.status, position, average)
            if job.status == "quota_wait":
                text = (
                    f"Tu historia está en la posición {position}.\n{job.wait_reason}.\n"
                    f"Próxima revisión: {job.not_before} (UTC). Tu idea está guardada."
                )
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
