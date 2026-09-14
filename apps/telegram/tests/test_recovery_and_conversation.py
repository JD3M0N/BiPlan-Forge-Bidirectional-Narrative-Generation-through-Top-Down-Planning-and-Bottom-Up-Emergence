import asyncio
import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest
from asg_telegram import app as app_module
from asg_telegram.app import TelegramStoryBot
from asg_telegram.config import TelegramConfigurationError
from asg_telegram.contract import GenerationProgress, ProfileOption, RunSummary
from asg_telegram.generators import summarize_run
from asg_telegram.queue import SCHEMA_VERSION, QueueRepository
from asg_telegram.states import ConversationState
from asg_top_down.errors import ConfigurationError

PROFILES = (
    ProfileOption("essential", "Esencial", ("essential", "esencial")),
    ProfileOption("developed", "Desarrollada", ("developed", "desarrollada")),
    ProfileOption("expansive", "Expansiva", ("expansive", "expansiva")),
)


class FakeBot:
    def __init__(self):
        self.messages = []
        self.edits = []

    async def send_message(self, **kwargs):
        self.messages.append(kwargs)
        return SimpleNamespace(message_id=len(self.messages))

    async def send_document(self, **kwargs):
        return None

    async def edit_message_text(self, **kwargs):
        self.edits.append(kwargs)


class RecordingGenerator:
    display_name = "Fake"
    profiles = PROFILES

    def __init__(self, story_directory: Path):
        self.story_directory = story_directory
        self.calls = []

    def generate(
        self,
        prompt,
        *,
        narrative_profile=None,
        on_progress=None,
        on_run_created=None,
        on_event=None,
    ):
        self.calls.append({"prompt": prompt, "narrative_profile": narrative_profile})
        return self.story_directory

    def summarize(self, run_dir):
        return RunSummary()


class BrokenGenerator(RecordingGenerator):
    def generate(self, prompt, **kwargs):
        raise RuntimeError("el proveedor devolvió basura")


def make_story(tmp_path: Path) -> Path:
    directory = tmp_path / "story"
    directory.mkdir()
    (directory / "story.md").write_text("# Historia\n\nContenido", encoding="utf-8")
    return directory


def make_update(user_id=7, chat_id=70, text="Un relato", replies=None):
    sent = replies if replies is not None else []

    async def reply_text(text, **kwargs):
        sent.append(text)
        return SimpleNamespace(message_id=100 + len(sent))

    return SimpleNamespace(
        effective_user=SimpleNamespace(id=user_id, username="ana", full_name="Ana"),
        effective_chat=SimpleNamespace(id=chat_id),
        effective_message=SimpleNamespace(text=text, reply_text=reply_text),
        callback_query=None,
    )


def make_context(bot, user_data=None):
    tasks = []
    application = SimpleNamespace(
        bot=bot,
        create_task=lambda coro, update=None: tasks.append(coro),
        user_data={},
    )
    context = SimpleNamespace(bot=bot, application=application, user_data=user_data or {})
    return context, tasks


# --- unexpected failures -----------------------------------------------------


def test_unexpected_error_names_the_job_and_does_not_say_unknown(tmp_path):
    queue = QueueRepository(tmp_path / "q.sqlite3")
    job = queue.enqueue(user_id=11, username="ana", chat_id=20, prompt="Una historia").job
    handler = TelegramStoryBot(BrokenGenerator(make_story(tmp_path)), queue)
    bot = FakeBot()
    context, _ = make_context(bot)
    user = SimpleNamespace(id=11, username="ana", full_name="Ana")

    asyncio.run(
        handler._generate_and_deliver(
            context=context,
            chat_id=20,
            user=user,
            prompt="Una historia",
            progress_message_id=99,
            job_id=job.id,
        )
    )

    notice = next(
        message["text"] for message in bot.messages if "UNEXPECTED_ERROR" in message["text"]
    )
    assert job.id in notice
    progress = next(edit["text"] for edit in bot.edits if "Generación fallida" in edit["text"])
    assert "unknown" not in progress
    assert "antes de comenzar" in progress
    assert queue.get(job.id).error_code == "UNEXPECTED_ERROR"


# --- cooperative cancellation ------------------------------------------------


def test_running_generation_stops_when_the_user_cancels(tmp_path):
    queue = QueueRepository(tmp_path / "q.sqlite3")
    job = queue.enqueue(user_id=11, username="ana", chat_id=20, prompt="Una historia").job
    story = make_story(tmp_path)

    class CancellingGenerator(RecordingGenerator):
        def generate(self, prompt, *, on_progress=None, **kwargs):
            on_progress(GenerationProgress(10, "analysis", "Analizando"))
            queue.request_cancellation(job.id)
            on_progress(GenerationProgress(20, "world", "Construyendo el mundo"))
            raise AssertionError("la generación debió detenerse")

    handler = TelegramStoryBot(CancellingGenerator(story), queue)
    bot = FakeBot()
    context, _ = make_context(bot)
    user = SimpleNamespace(id=11, username="ana", full_name="Ana")

    asyncio.run(
        handler._generate_and_deliver(
            context=context,
            chat_id=20,
            user=user,
            prompt="Una historia",
            progress_message_id=99,
            job_id=job.id,
        )
    )

    assert queue.get(job.id).status == "cancelled"
    assert queue.get(job.id).error_code == "CANCELLED_BY_USER"
    assert any("Cancelaste la generación" in message["text"] for message in bot.messages)


# --- restart recovery --------------------------------------------------------


def test_interrupted_job_is_requeued_once_then_reported_as_exhausted(tmp_path):
    path = tmp_path / "q.sqlite3"
    queue = QueueRepository(path)
    job = queue.enqueue(user_id=11, username="ana", chat_id=20, prompt="Una historia").job
    queue.mark_running(job.id)

    handler = TelegramStoryBot(RecordingGenerator(make_story(tmp_path)), queue)
    bot = FakeBot()
    application = SimpleNamespace(
        bot=bot, create_task=lambda coro: coro.close(), user_data={11: {}}
    )

    asyncio.run(handler.restore_queue(application))

    assert queue.get(job.id).status == "queued"
    assert queue.recovery_pending() == []
    assert any("volveré a generar" in message["text"] for message in bot.messages)

    queue.mark_running(job.id)
    second_bot = FakeBot()
    second_application = SimpleNamespace(
        bot=second_bot, create_task=lambda coro: coro.close(), user_data={11: {}}
    )
    asyncio.run(handler.restore_queue(second_application))

    assert queue.get(job.id).status == "failed"
    assert queue.get(job.id).error_code == "RECOVERY_EXHAUSTED"
    assert queue.recovery_pending() == []
    assert any("RECOVERY_EXHAUSTED" in message["text"] for message in second_bot.messages)


# --- schema migration --------------------------------------------------------


def test_a_legacy_database_migrates_once_and_keeps_its_jobs(tmp_path):
    """A pre-migration database keeps its jobs, gains the new columns, and reopens cleanly."""
    path = tmp_path / "legacy.sqlite3"
    legacy = sqlite3.connect(path)
    legacy.execute(
        """CREATE TABLE jobs (
            id TEXT PRIMARY KEY, user_id INTEGER NOT NULL,
            username TEXT NOT NULL, chat_id INTEGER NOT NULL,
            prompt TEXT NOT NULL, status TEXT NOT NULL,
            enqueued_at TEXT NOT NULL, started_at TEXT, finished_at TEXT,
            progress_message_id INTEGER, run_dir TEXT,
            recovery_count INTEGER NOT NULL DEFAULT 0,
            duration_seconds REAL, error_code TEXT
        )"""
    )
    legacy.execute(
        "INSERT INTO jobs(id,user_id,username,chat_id,prompt,status,enqueued_at) "
        "VALUES('legacy-1',11,'ana',20,'Una historia','queued','2026-01-01')"
    )
    legacy.commit()
    legacy.close()

    queue = QueueRepository(path)

    restored = queue.get("legacy-1")
    assert restored is not None
    assert restored.prompt == "Una historia"
    assert restored.narrative_profile is None
    assert restored.cancel_requested == 0
    with queue._connect() as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION

    # Reopening must neither re-migrate nor duplicate, and the new column round-trips.
    job = queue.enqueue(
        user_id=12,
        username="luis",
        chat_id=21,
        prompt="Otra historia",
        narrative_profile="expansive",
    ).job
    reopened = QueueRepository(path)
    assert len(reopened.active()) == 2
    assert reopened.get(job.id).narrative_profile == "expansive"


# --- conversation handlers ---------------------------------------------------


def test_conversation_routes_text_by_state(tmp_path):
    """`/newstory` opens the mode choice; text with no state is pointed back at the command."""
    handler = TelegramStoryBot(RecordingGenerator(make_story(tmp_path)))

    replies: list = []
    context, _ = make_context(FakeBot())
    asyncio.run(handler.new_story(make_update(replies=replies), context))
    assert context.user_data["state"] == ConversationState.CHOOSE_MODE
    assert "¿Cómo quieres describir la historia?" in replies

    stray: list = []
    stateless, _ = make_context(FakeBot())
    asyncio.run(handler.text_input(make_update(replies=stray), stateless))
    assert stray == ["Usa /newstory para crear una historia."]


def test_guided_flow_validates_and_sends_the_chosen_profile(tmp_path):
    """An invalid profile answer does not advance the flow; the valid one reaches the generator."""
    generator = RecordingGenerator(make_story(tmp_path))
    handler = TelegramStoryBot(generator)
    replies: list = []
    context, tasks = make_context(FakeBot(), {"state": ConversationState.GUIDED})
    context.user_data.update(guided_index=0, guided_values={})

    answers = [
        "español",
        "fantasía",
        "una cartógrafa",
        "las estrellas desaparecen",
        "una estación orbital",
        "melancólico",
    ]
    for answer in answers:
        asyncio.run(handler.text_input(make_update(text=answer, replies=replies), context))

    # The profile question is next: a bad answer is rejected without advancing.
    assert context.user_data["guided_index"] == 6
    asyncio.run(handler.text_input(make_update(text="gigantesca", replies=replies), context))
    assert "Esencial, Desarrollada, Expansiva" in replies[-1]
    assert context.user_data["guided_index"] == 6

    for answer in ("Esencial", "ninguna"):
        asyncio.run(handler.text_input(make_update(text=answer, replies=replies), context))

    assert len(tasks) == 1
    asyncio.run(tasks[0])
    assert generator.calls[0]["narrative_profile"] == "essential"
    assert "Perfil narrativo: Esencial" in generator.calls[0]["prompt"]


def test_cancel_reports_each_possible_outcome(tmp_path):
    queue = QueueRepository(tmp_path / "q.sqlite3")
    handler = TelegramStoryBot(RecordingGenerator(make_story(tmp_path)), queue)
    replies: list = []
    context, _ = make_context(FakeBot())

    asyncio.run(handler.cancel(make_update(replies=replies), context))
    assert "No hay ningún proceso activo." in replies[-1]

    job = queue.enqueue(user_id=7, username="ana", chat_id=70, prompt="a").job
    asyncio.run(handler.cancel(make_update(replies=replies), context))
    assert "retirada de la cola" in replies[-1]

    second = queue.enqueue(user_id=7, username="ana", chat_id=70, prompt="b").job
    queue.mark_running(second.id)
    asyncio.run(handler.cancel(make_update(replies=replies), context))
    assert "Pedí detener la generación" in replies[-1]
    assert queue.cancellation_requested(second.id)
    assert queue.get(job.id).status == "cancelled"


def test_a_second_request_is_refused_instead_of_silently_dropped(tmp_path):
    queue = QueueRepository(tmp_path / "q.sqlite3")
    queue.enqueue(user_id=7, username="ana", chat_id=70, prompt="la primera")
    handler = TelegramStoryBot(RecordingGenerator(make_story(tmp_path)), queue)
    replies: list = []
    context, tasks = make_context(FakeBot())

    asyncio.run(handler._launch_generation(make_update(replies=replies), context, "la segunda"))

    assert tasks == []
    assert "no encolé esta" in replies[-1]
    assert 7 not in handler.active_users


# --- start-up validation -----------------------------------------------------


def _break_top_down_configuration(monkeypatch, tmp_path):
    """Make the Top-Down generator fail to build while Telegram settings load fine."""
    monkeypatch.setattr(
        app_module,
        "load_settings",
        lambda: SimpleNamespace(
            telegram_token="t", generator_name="top-down", project_root=tmp_path
        ),
    )

    def explode(_name):
        raise ConfigurationError("Falta GEMINI_API_KEY.")

    monkeypatch.setattr(app_module, "create_generator", explode)


def _break_telegram_settings(monkeypatch, tmp_path):
    """Make the Telegram settings themselves fail to load."""

    def explode():
        raise TelegramConfigurationError("Falta TELEGRAM_BOT_TOKEN.")

    monkeypatch.setattr(app_module, "load_settings", explode)


@pytest.mark.parametrize(
    "break_configuration",
    [_break_top_down_configuration, _break_telegram_settings],
    ids=["broken-top-down-configuration", "missing-telegram-token"],
)
def test_main_reports_broken_configuration_as_exit_code_two(
    monkeypatch, tmp_path, break_configuration
):
    break_configuration(monkeypatch, tmp_path)
    assert app_module.main([]) == 2


# --- run summaries -----------------------------------------------------------


@pytest.mark.parametrize(
    "prepare",
    [
        lambda run: None,
        lambda run: (
            (run / "metadata.json").write_text("{no es json", encoding="utf-8"),
            (run / "llm_usage_summary.json").write_text(json.dumps([1, 2]), encoding="utf-8"),
        ),
    ],
    ids=["no-json-artifacts-at-all", "broken-json-artifacts"],
)
def test_summary_survives_missing_or_broken_artifacts(tmp_path, prepare):
    run = tmp_path / "run"
    run.mkdir()
    prepare(run)

    summary = summarize_run(run)
    assert summary.usage is None
    assert summary.warnings == ()


# --- queue refresh between users ---------------------------------------------


def test_enqueueing_does_not_overwrite_the_running_users_progress_bar(tmp_path):
    """A second user joining the queue must leave the live progress bar of the first alone."""
    queue = QueueRepository(tmp_path / "q.sqlite3")
    running = queue.enqueue(
        user_id=11, username="ana", chat_id=20, prompt="Una historia", progress_message_id=99
    ).job
    queue.mark_running(running.id)
    queue.enqueue(
        user_id=12, username="beto", chat_id=21, prompt="Otra historia", progress_message_id=77
    )

    handler = TelegramStoryBot(RecordingGenerator(make_story(tmp_path)), queue)
    bot = FakeBot()
    context, _ = make_context(bot)

    asyncio.run(handler._refresh_queue(context.application))

    assert [edit["message_id"] for edit in bot.edits] == [77]
    # The running job still counts, so the waiting user is told position 2 and not position 1.
    assert "posición 2" in bot.edits[0]["text"]


def test_the_queued_to_running_transition_still_edits_the_running_message(tmp_path):
    """Skipping the running job everywhere else must not silence the moment it starts."""
    queue = QueueRepository(tmp_path / "q.sqlite3")
    running = queue.enqueue(
        user_id=11, username="ana", chat_id=20, prompt="Una historia", progress_message_id=99
    ).job
    queue.mark_running(running.id)

    handler = TelegramStoryBot(RecordingGenerator(make_story(tmp_path)), queue)
    bot = FakeBot()
    context, _ = make_context(bot)

    asyncio.run(handler._refresh_queue(context.application, include_running=True))

    assert [edit["message_id"] for edit in bot.edits] == [99]
    assert "se está generando ahora" in bot.edits[0]["text"]
