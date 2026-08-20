"""Bot de Telegram para generar historias y registrar evaluaciones."""

from __future__ import annotations

import asyncio
import inspect
import logging
from pathlib import Path
from types import SimpleNamespace

from asg_evaluation import METRICS, add_evaluation
from asg_top_down.progress import ProgressUpdate, format_progress
from asg_top_down.errors import ASGError
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.error import BadRequest, NetworkError, TelegramError
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from .config import TelegramConfigurationError, load_settings
from .console import configure_console_logging, log_user_action
from .generators import StoryGenerator, create_generator
from .prompts import (
    GUIDED_FIELDS,
    METRIC_EXPLANATIONS,
    build_guided_prompt,
    telegram_story_chunks,
    validate_guided_value,
)
from .queue import QueueRepository

LOGGER = logging.getLogger(__name__)
DOCUMENT_RETRY_DELAYS = (1, 2, 4)
EXAMPLE_PROMPT = (
    "Escribe un relato de ciencia ficción de unas 1800 palabras sobre una "
    "cartógrafa que descubre un mensaje en las estrellas. Tono melancólico "
    "y final esperanzador."
)


def _user_log(
    update: Update, action: str, category: str = "acción"
) -> None:
    user = update.effective_user
    if user is None:
        log_user_action(
            LOGGER,
            user_id=None,
            username=None,
            action=action,
            category=category,
        )
        return
    readable = user.username or user.full_name or "sin nombre"
    log_user_action(
        LOGGER,
        user_id=user.id,
        username=readable,
        action=action,
        category=category,
    )


def _mode_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[
            InlineKeyboardButton("Prompt libre", callback_data="mode:free"),
            InlineKeyboardButton("Asistente guiado", callback_data="mode:guided"),
        ]]
    )


def _score_keyboard(metric: str) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(str(score), callback_data=f"score:{metric}:{score}")
            for score in range(start, min(start + 5, 11))
        ]
        for start in (1, 6)
    ]
    return InlineKeyboardMarkup(rows)


class TelegramStoryBot:
    def __init__(self, generator: StoryGenerator, queue: QueueRepository | None = None) -> None:
        self.generator = generator
        self.queue = queue
        self.active_users: set[int] = set()
        self.delivery_semaphore = asyncio.Semaphore(1)
        self.generation_semaphore = asyncio.Semaphore(1)

    async def restore_queue(self, application) -> None:
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
                bot=application.bot, application=application,
                user_data=application.user_data[job.user_id],
            )
            application.create_task(self._generate_and_deliver(
                context=context, chat_id=job.chat_id, user=user, prompt=job.prompt,
                progress_message_id=job.progress_message_id, job_id=job.id,
            ))
        await self._refresh_queue(application)

    async def start(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        _user_log(update, "ejecutó /start")
        await update.effective_message.reply_text(
            "¡Hola! Puedo crear historias con el enfoque "
            f"{self.generator.display_name} y luego recoger tu evaluación.\n\n"
            "Usa /newstory para comenzar o /help para ver los comandos."
        )

    async def help(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        _user_log(update, "ejecutó /help")
        await update.effective_message.reply_text(
            "/newstory — crear una historia\n"
            "/cancel — abandonar la solicitud o evaluación actual\n"
            "/help — mostrar esta ayuda"
        )

    async def new_story(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        user_id = update.effective_user.id
        _user_log(update, "ejecutó /newstory")
        if user_id in self.active_users:
            _user_log(update, "intentó iniciar otra generación mientras tenía una activa")
            await update.effective_message.reply_text(
                "Ya estoy generando una historia para ti. Espera a que termine."
            )
            return
        context.user_data.clear()
        context.user_data["state"] = "choose_mode"
        await update.effective_message.reply_text(
            "¿Cómo quieres describir la historia?",
            reply_markup=_mode_keyboard(),
        )

    async def cancel(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        user_id = update.effective_user.id
        _user_log(update, "ejecutó /cancel")
        if self.queue and self.queue.cancel_user(user_id):
            self.active_users.discard(user_id)
            context.user_data.clear()
            await update.effective_message.reply_text(
                "Tu solicitud fue retirada de la cola. Puedes usar /newstory cuando quieras."
            )
            await self._refresh_queue(context.application)
            return
        if user_id in self.active_users:
            await update.effective_message.reply_text(
                "La generación o entrega ya está en curso y no puede cancelarse. "
                "Te avisaré cuando termine."
            )
            return
        had_state = bool(context.user_data.get("state"))
        context.user_data.clear()
        await update.effective_message.reply_text(
            "Proceso cancelado. Puedes usar /newstory cuando quieras."
            if had_state
            else "No hay ningún proceso activo."
        )

    async def choose_mode(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        query = update.callback_query
        await query.answer()
        if context.user_data.get("state") != "choose_mode":
            await query.edit_message_text("Esta selección ya no está activa.")
            return
        mode = query.data.split(":", 1)[1]
        _user_log(update, f"seleccionó el modo {mode}")
        if mode == "free":
            context.user_data["state"] = "free_prompt"
            await query.edit_message_text(
                f"Envía una descripción completa.\n\nEjemplo:\n{EXAMPLE_PROMPT}"
            )
            return
        context.user_data.update(
            state="guided",
            guided_index=0,
            guided_values={},
        )
        await query.edit_message_text(GUIDED_FIELDS[0][1])

    async def text_input(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        state = context.user_data.get("state")
        text = update.effective_message.text
        if state == "free_prompt":
            _user_log(update, "envió un prompt libre")
            if not text.strip():
                await update.effective_message.reply_text(
                    "La descripción no puede estar vacía."
                )
                return
            await self._launch_generation(update, context, text.strip())
        elif state == "guided":
            await self._guided_input(update, context, text)
        elif state == "evaluating":
            _user_log(update, "envió texto durante la evaluación")
            await update.effective_message.reply_text(
                "Selecciona una puntuación usando los botones del 1 al 10."
            )
        else:
            await update.effective_message.reply_text(
                "Usa /newstory para crear una historia."
            )

    async def _guided_input(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE, text: str
    ) -> None:
        index = context.user_data["guided_index"]
        field, _ = GUIDED_FIELDS[index]
        _user_log(update, f"respondió el campo guiado {field}")
        try:
            value = validate_guided_value(field, text)
        except ValueError as exc:
            await update.effective_message.reply_text(str(exc))
            return
        context.user_data["guided_values"][field] = value
        index += 1
        context.user_data["guided_index"] = index
        if index < len(GUIDED_FIELDS):
            await update.effective_message.reply_text(GUIDED_FIELDS[index][1])
            return
        prompt = build_guided_prompt(context.user_data["guided_values"])
        await self._launch_generation(update, context, prompt)

    async def _launch_generation(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE, prompt: str
    ) -> None:
        user_id = update.effective_user.id
        if user_id in self.active_users:
            await update.effective_message.reply_text(
                "Ya hay una generación activa para ti."
            )
            return
        self.active_users.add(user_id)
        _user_log(
            update,
            f"Inició una generación {self.generator.display_name}",
            category="generación",
        )
        context.user_data.clear()
        context.user_data["state"] = "generating"
        progress_message = await update.effective_message.reply_text(
            format_progress(ProgressUpdate(
                percent=0,
                stage="starting",
                description=f"Iniciando generación {self.generator.display_name}",
            ))
        )
        job_id = None
        if self.queue:
            job = self.queue.enqueue(
                user_id=user_id,
                username=update.effective_user.username or update.effective_user.full_name,
                chat_id=update.effective_chat.id, prompt=prompt,
                progress_message_id=progress_message.message_id,
            )
            job_id = job.id
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
        loop = asyncio.get_running_loop()
        last_progress: list[ProgressUpdate] = []

        def report_progress(update: ProgressUpdate) -> None:
            last_progress[:] = [update]
            if progress_message_id is None:
                return
            future = asyncio.run_coroutine_threadsafe(
                self._safe_edit_progress(
                    context, chat_id, progress_message_id, format_progress(update)
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
                    context=context, chat_id=chat_id, user=user, prompt=prompt,
                    progress_message_id=progress_message_id, job_id=job_id,
                    report_progress=report_progress, last_progress=last_progress,
                )
        finally:
            self.active_users.discard(user.id)
            if self.queue:
                await self._refresh_queue(context.application)

    async def _run_generation_and_delivery(
        self, *, context, chat_id, user, prompt, progress_message_id,
        job_id, report_progress, last_progress,
    ) -> None:
        try:
            try:
                parameters = inspect.signature(self.generator.generate).parameters
                run_created = (
                    (lambda path: self.queue.set_run_dir(job_id, str(path)))
                    if job_id and self.queue else None
                )
                args = (
                    (prompt, report_progress, run_created) if len(parameters) >= 3
                    else (prompt, report_progress) if len(parameters) >= 2 else (prompt,)
                )
                operation = self.generator.generate
                story_directory = await asyncio.to_thread(
                    operation, *args
                )
            except Exception as exc:
                if job_id and self.queue:
                    self.queue.finish(job_id, "failed", error_code=getattr(exc, "code", "UNEXPECTED_ERROR"))
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
                    await self._safe_edit_progress(
                        context,
                        chat_id,
                        progress_message_id,
                        format_progress(ProgressUpdate(
                            percent=percent,
                            stage="failed",
                            description=(
                                f"{getattr(exc, 'stage', last_progress[-1].stage if last_progress else 'unknown')}: "
                                f"{getattr(exc, 'summary', 'Generación fallida')}"
                            )[:180],
                        )),
                    )
                context.user_data.clear()
                await self._safe_notice(
                    context,
                    chat_id,
                    exc.public_message() if isinstance(exc, ASGError) else (
                        "No pude generar la historia por un error interno inesperado. "
                        "Consulta el registro de la consola y vuelve a intentarlo. "
                        "Código: UNEXPECTED_ERROR."
                    ),
                    user,
                )
                return
            if job_id and self.queue:
                self.queue.set_run_dir(job_id, str(story_directory))
            log_user_action(
                LOGGER,
                user_id=user.id,
                username=user.username or user.full_name,
                action=f"Generación terminada y guardada en {story_directory}",
                category="éxito",
            )
            usage_path = Path(story_directory) / "llm_usage_summary.json"
            if progress_message_id is not None and usage_path.is_file():
                try:
                    import json
                    usage = json.loads(usage_path.read_text(encoding="utf-8"))
                    await self._safe_edit_progress(
                        context, chat_id, progress_message_id,
                        "[██████████] 100% — Historia terminada\n"
                        f"Gemini: {usage.get('calls', 0)} llamadas, "
                        f"{usage.get('total_tokens', 0)} tokens, "
                        f"{round(usage.get('total_wait_seconds', 0))}s esperando cuota.",
                    )
                except (OSError, ValueError):
                    pass
            metadata_path = Path(story_directory) / "metadata.json"
            if metadata_path.is_file():
                try:
                    import json
                    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
                    warnings = metadata.get("warnings", [])
                    if warnings:
                        log_user_action(
                            LOGGER,
                            user_id=user.id,
                            username=user.username or user.full_name,
                            action="Historia completada con advertencias de calidad",
                            category="advertencia",
                            level=logging.WARNING,
                        )
                        await self._safe_notice(
                            context, chat_id,
                            "La historia se completó, pero la revisión automática dejó esta "
                            f"advertencia: {warnings[0]}",
                            user,
                        )
                except (OSError, ValueError, TypeError):
                    LOGGER.warning("No se pudieron leer las advertencias de la ejecución")
            story_path = Path(story_directory) / "story.md"
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
                        story_path=story_path,
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
                    context.user_data.update(
                        state="evaluating",
                        story_directory=str(story_directory),
                        metric_index=0,
                        scores={},
                        evaluator=_evaluator_name(user),
                    )
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text=(
                            "Ahora evalúa la historia. Cada parámetro se puntúa del "
                            "1 (mínimo) al 10 (máximo). Usa /cancel si quieres abandonar."
                        ),
                    )
                    await self._ask_metric(context, chat_id)
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

    async def _refresh_queue(self, application) -> None:
        if not self.queue:
            return
        jobs = self.queue.active()
        average = self.queue.average_duration()
        for position, job in enumerate(jobs, 1):
            if job.status == "running":
                text = "Tu historia se está generando ahora. Posición 1."
            else:
                estimate = "estimación aún no disponible"
                if average:
                    low = max(1, round((position - 1) * average * .8 / 60))
                    high = max(low, round((position - 1) * average * 1.2 / 60))
                    estimate = f"{low}–{high} minutos"
                text = (
                    f"Tu historia está en la posición {position}.\n"
                    f"Tiempo estimado: {estimate}.\n"
                    "Te avisaré automáticamente cuando avance."
                )
            if job.progress_message_id:
                try:
                    await application.bot.edit_message_text(
                        chat_id=job.chat_id, message_id=job.progress_message_id, text=text,
                    )
                except TelegramError:
                    try:
                        message = await application.bot.send_message(chat_id=job.chat_id, text=text)
                        self.queue.set_progress_message(job.id, message.message_id)
                    except TelegramError:
                        pass

    async def _safe_edit_progress(
        self, context, chat_id: int, message_id: int, text: str
    ) -> None:
        try:
            await context.bot.edit_message_text(
                chat_id=chat_id, message_id=message_id, text=text
            )
        except BadRequest as exc:
            if "message is not modified" not in str(exc).lower():
                LOGGER.warning("No se pudo actualizar el progreso: %s", exc)
        except TelegramError as exc:
            LOGGER.warning("No se pudo actualizar el progreso: %s", exc)

    async def _deliver_story(
        self, *, context, chat_id: int, user, story_path: Path
    ) -> bool:
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
        self, *, context, chat_id: int, user, story_path: Path
    ) -> bool:
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
                log_user_action(
                    LOGGER,
                    user_id=user.id,
                    username=user.username or user.full_name,
                    action="Telegram rechazó permanentemente el archivo",
                    category="error",
                    level=logging.ERROR,
                    exc_info=True,
                )
                return False
            except NetworkError:
                if attempt == attempts:
                    log_user_action(
                        LOGGER,
                        user_id=user.id,
                        username=user.username or user.full_name,
                        action="Se agotaron los reintentos del archivo",
                        category="error",
                        level=logging.ERROR,
                        exc_info=True,
                    )
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
                log_user_action(
                    LOGGER,
                    user_id=user.id,
                    username=user.username or user.full_name,
                    action="Telegram rechazó permanentemente el archivo",
                    category="error",
                    level=logging.ERROR,
                    exc_info=True,
                )
                return False
        return False

    async def _safe_notice(self, context, chat_id: int, text: str, user) -> None:
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

    async def _ask_metric(self, context, chat_id: int) -> None:
        metric = METRICS[context.user_data["metric_index"]]
        explanation = METRIC_EXPLANATIONS[metric].message()
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"{explanation}\n\nElige una puntuación:",
            parse_mode=ParseMode.HTML,
            reply_markup=_score_keyboard(metric),
        )

    async def score(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        query = update.callback_query
        if context.user_data.get("state") != "evaluating":
            await query.answer()
            await query.edit_message_text("Esta evaluación ya no está activa.")
            return
        _, metric, raw_score = query.data.split(":")
        expected = METRICS[context.user_data["metric_index"]]
        if metric != expected:
            await query.answer("Esa pregunta ya fue respondida.", show_alert=True)
            return
        score = int(raw_score)
        if not 1 <= score <= 10:
            await query.answer("La puntuación debe estar entre 1 y 10.", show_alert=True)
            return
        await query.answer()
        _user_log(update, f"puntuó {metric} con {score}/10")
        context.user_data["scores"][metric] = score
        explanation = METRIC_EXPLANATIONS[metric].message()
        await query.edit_message_text(
            f"{explanation}\n\nPuntuación elegida: <b>{score}/10</b>",
            parse_mode=ParseMode.HTML,
        )
        context.user_data["metric_index"] += 1
        if context.user_data["metric_index"] < len(METRICS):
            await self._ask_metric(context, update.effective_chat.id)
            return
        await self._save_evaluation(update, context)

    async def _save_evaluation(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        scores = dict(context.user_data["scores"])
        story_directory = context.user_data["story_directory"]
        evaluator = context.user_data["evaluator"]
        try:
            await asyncio.to_thread(
                add_evaluation, story_directory, evaluator, scores
            )
        except Exception:
            LOGGER.exception("No se pudo guardar una evaluación")
            await update.effective_message.reply_text(
                "No pude guardar la evaluación. Intenta responder de nuevo."
            )
            context.user_data["metric_index"] = len(METRICS) - 1
            context.user_data["scores"].pop(METRICS[-1], None)
            await self._ask_metric(context, update.effective_chat.id)
            return
        summary = "\n".join(
            f"• {metric}: {scores[metric]}/10" for metric in METRICS
        )
        context.user_data.clear()
        _user_log(update, "completó y guardó la evaluación")
        await update.effective_message.reply_text(
            f"¡Gracias! Evaluación guardada:\n{summary}\n\n"
            "Usa /newstory para crear otra historia."
        )


def _evaluator_name(user) -> str:
    readable = user.username or user.full_name or "sin nombre"
    return f"telegram:{user.id} ({readable})"


def build_application(token: str, bot: TelegramStoryBot) -> Application:
    async def post_init(application) -> None:
        await bot.restore_queue(application)

    application = (
        Application.builder()
        .token(token)
        .connect_timeout(15)
        .read_timeout(30)
        .write_timeout(30)
        .media_write_timeout(60)
        .pool_timeout(10)
        .concurrent_updates(True)
        .post_init(post_init)
        .build()
    )
    application.add_handler(CommandHandler("start", bot.start))
    application.add_handler(CommandHandler("help", bot.help))
    application.add_handler(CommandHandler("newstory", bot.new_story))
    application.add_handler(CommandHandler("cancel", bot.cancel))
    application.add_handler(
        CallbackQueryHandler(bot.choose_mode, pattern=r"^mode:(free|guided)$")
    )
    application.add_handler(
        CallbackQueryHandler(
            bot.score,
            pattern=r"^score:(coherence|pacing|creativity|engagement|relevance|satisfaction):(?:10|[1-9])$",
        )
    )
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, bot.text_input)
    )
    return application


def main() -> int:
    configure_console_logging()
    try:
        settings = load_settings()
        generator = create_generator(settings.generator_name)
        application = build_application(
            settings.telegram_token,
            TelegramStoryBot(
                generator,
                QueueRepository(settings.project_root / "Stories" / "telegram_queue.sqlite3"),
            ),
        )
    except (TelegramConfigurationError, ValueError) as exc:
        LOGGER.error("%s", exc)
        return 2
    LOGGER.info("Iniciando bot con el generador %s", generator.display_name)
    try:
        application.run_polling(allowed_updates=Update.ALL_TYPES)
    except TelegramError as exc:
        LOGGER.error("No se pudo conectar con Telegram: %s", exc)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
