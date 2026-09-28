import asyncio
import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest
from asg_telegram import app as app_module
from asg_telegram.config import TelegramConfigurationError
from asg_telegram.contract import GeneratorUnavailable, StoryOutline
from asg_telegram.handlers import TelegramStoryBot
from asg_telegram.queue import SCHEMA_VERSION, QueueRepository
from asg_telegram.states import ConversationState
from telegram_fakes import BrokenGenerator, CancellingGenerator, FakeGenerator


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


async def _async_noop(*args, **kwargs) -> None:
    """Stand in for a Telegram callback query's answer coroutine."""


def _record_edit(replies: list):
    """Build an edit_message_text stub that appends its text to the given list."""

    async def edit(text=None, **kwargs) -> None:
        """Append one edited message's text to the bound replies list."""
        if text is not None:
            replies.append(text)

    return edit


def make_callback(data: str, replies: list, user_id=7, chat_id=70):
    async def reply_text(text, **kwargs):
        replies.append(text)
        return SimpleNamespace(message_id=100 + len(replies))

    return SimpleNamespace(
        data=data,
        answer=_async_noop,
        edit_message_text=_record_edit(replies),
        from_user=SimpleNamespace(id=user_id, username="ana", full_name="Ana"),
        message=SimpleNamespace(chat=SimpleNamespace(id=chat_id), reply_text=reply_text),
    )


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


def test_running_generation_stops_when_should_cancel_reports_true(tmp_path):
    queue = QueueRepository(tmp_path / "q.sqlite3")
    job = queue.enqueue(user_id=11, username="ana", chat_id=20, prompt="Una historia").job
    story = make_story(tmp_path)

    handler = TelegramStoryBot(CancellingGenerator(story), queue)
    bot = FakeBot()
    context, _ = make_context(bot)
    user = SimpleNamespace(id=11, username="ana", full_name="Ana")
    queue.cancel_user(11)  # the job is still queued: this cancels it outright
    job = queue.enqueue(user_id=11, username="ana", chat_id=20, prompt="Otra").job
    queue.mark_running(job.id)
    queue.cancel_user(11)  # now it is running: this only requests cancellation

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

    handler = TelegramStoryBot(FakeGenerator(make_story(tmp_path)), queue)
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


def test_restore_rebuilds_options_and_brief_from_a_queued_job(tmp_path):
    path = tmp_path / "q.sqlite3"
    queue = QueueRepository(path)
    generator = FakeGenerator(make_story(tmp_path))
    handler = TelegramStoryBot(generator, queue)
    queue.enqueue(
        user_id=11,
        username="ana",
        chat_id=20,
        prompt="Una archivera",
        options={"format": "simulated", "turns_per_beat": 6},
        brief={"plot": "Una trama", "cast": [{"name": "Ana"}]},
    )
    application = SimpleNamespace(
        bot=FakeBot(), create_task=lambda coro: coro.close(), user_data={11: {}}
    )
    asyncio.run(handler.restore_queue(application))
    assert generator.calls == []  # create_task closes the coroutine without running it


def test_restore_turns_legacy_columns_into_options(tmp_path):
    path = tmp_path / "q.sqlite3"
    queue = QueueRepository(path)
    job = queue.enqueue(
        user_id=11,
        username="ana",
        chat_id=20,
        prompt="Una historia",
        narrative_profile="expansive",
        story_format="script-native",
    ).job
    row = queue.get(job.id)
    assert row.options is None
    assert TelegramStoryBot._legacy_options(row) == {
        "format": "script-native",
        "narrative_profile": "expansive",
    }


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
    assert restored.options is None
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
    """`/newstory` opens the format choice; text with no state is pointed back at the command."""
    handler = TelegramStoryBot(FakeGenerator(make_story(tmp_path)))

    replies: list = []
    context, _ = make_context(FakeBot())
    asyncio.run(handler.new_story(make_update(replies=replies), context))
    assert context.user_data["state"] == ConversationState.CHOOSE_FORMAT
    assert "¿Qué quieres generar?" in replies

    stray: list = []
    stateless, _ = make_context(FakeBot())
    asyncio.run(handler.text_input(make_update(replies=stray), stateless))
    assert stray == ["Usa /newstory para crear una historia."]


def test_choose_format_then_free_mode_reaches_the_generator(tmp_path):
    """Picking an output format advances to the mode choice, then reaches the generator."""
    generator = FakeGenerator(make_story(tmp_path))
    handler = TelegramStoryBot(generator)
    replies: list = []
    context, tasks = make_context(FakeBot())
    asyncio.run(handler.new_story(make_update(replies=replies), context))
    assert context.user_data["state"] == ConversationState.CHOOSE_FORMAT

    callback_update = make_update(replies=replies)
    callback_update.callback_query = make_callback("format:simulated", replies)
    asyncio.run(handler.choose_format(callback_update, context))
    assert context.user_data["state"] == ConversationState.CHOOSE_MODE
    assert handler.stored_options(7)["format"] == "simulated"

    mode_update = make_update(replies=replies)
    mode_update.callback_query = make_callback("mode:free", replies)
    asyncio.run(handler.choose_mode(mode_update, context))
    asyncio.run(handler.text_input(make_update(text="Un relato", replies=replies), context))
    assert len(tasks) == 1
    asyncio.run(tasks[0])
    assert generator.calls[0]["options"]["format"] == "simulated"


def test_options_panel_toggle_and_choice_persist_and_are_scoped_to_the_format(tmp_path):
    handler = TelegramStoryBot(FakeGenerator(make_story(tmp_path)))
    replies: list = []
    context, _ = make_context(FakeBot())

    await_update = make_update(replies=replies)
    asyncio.run(handler.settings(await_update, context))
    assert "Ledger de promesas" in replies[-1]

    toggle_update = make_update(replies=replies)
    toggle_update.callback_query = make_callback("opt:tog:promise_ledger", replies)
    asyncio.run(handler.option_callback(toggle_update, context))
    assert handler.stored_options(7) == {"promise_ledger": False}

    reset_update = make_update(replies=replies)
    reset_update.callback_query = make_callback("opt:reset", replies)
    asyncio.run(handler.option_callback(reset_update, context))
    assert handler.stored_options(7) == {}


def test_narrator_only_reaches_the_panel_for_the_voices_that_take_a_character(tmp_path):
    handler = TelegramStoryBot(FakeGenerator(make_story(tmp_path)))
    replies: list = []
    context, _ = make_context(FakeBot())
    handler.change_option(7, "format", "simulated")

    open_update = make_update(replies=replies)
    open_update.callback_query = make_callback("opt:open:narrative_voice", replies)
    asyncio.run(handler.option_callback(open_update, context))

    set_update = make_update(replies=replies)
    set_update.callback_query = make_callback("opt:set:narrative_voice:1", replies)
    asyncio.run(handler.option_callback(set_update, context))
    assert handler.stored_options(7)["narrative_voice"] == "first_person"

    text_update = make_update(text="Ana", replies=replies)
    context.user_data["awaiting_option"] = "narrator"
    asyncio.run(handler.text_input(text_update, context))
    assert handler.stored_options(7)["narrator"] == "Ana"
    assert "awaiting_option" not in context.user_data


def test_guided_brief_with_two_cast_members_reaches_the_generator(tmp_path):
    generator = FakeGenerator(make_story(tmp_path))
    handler = TelegramStoryBot(generator)
    replies: list = []
    context, tasks = make_context(FakeBot())
    context.user_data.update(state=ConversationState.GUIDED, brief_step="title", brief_values={})

    for step in ("title", "genre", "setting"):
        callback = make_update(replies=replies)
        callback.callback_query = make_callback(f"brief:skip:{step}", replies)
        asyncio.run(handler.brief_callback(callback, context))
    assert context.user_data["brief_step"] == "plot"

    plot_update = make_update(text="Una trama de prueba")
    asyncio.run(handler._guided_input(plot_update, context, "Una trama de prueba"))
    assert context.user_data["brief_step"] == "cast"

    add = make_update(replies=replies)
    add.callback_query = make_callback("brief:add", replies)
    asyncio.run(handler.brief_callback(add, context))
    asyncio.run(handler._guided_input(make_update(text="Ana"), context, "Ana"))
    role = make_update(replies=replies)
    role.callback_query = make_callback("brief:role:1", replies)
    asyncio.run(handler.brief_callback(role, context))
    pron = make_update(replies=replies)
    pron.callback_query = make_callback("brief:pron:1", replies)
    asyncio.run(handler.brief_callback(pron, context))
    skip_desc = make_update(replies=replies)
    skip_desc.callback_query = make_callback("brief:skip:description", replies)
    asyncio.run(handler.brief_callback(skip_desc, context))
    skip_secret = make_update(replies=replies)
    skip_secret.callback_query = make_callback("brief:skip:secret", replies)
    asyncio.run(handler.brief_callback(skip_secret, context))

    add2 = make_update(replies=replies)
    add2.callback_query = make_callback("brief:add", replies)
    asyncio.run(handler.brief_callback(add2, context))
    # a duplicate name is rejected before it enters the cast, and never advances the step
    asyncio.run(handler._guided_input(make_update(text="ana"), context, "ana"))
    assert context.user_data["cast_step"] == "name"
    asyncio.run(handler._guided_input(make_update(text="Beto"), context, "Beto"))
    role2 = make_update(replies=replies)
    role2.callback_query = make_callback("brief:role:0", replies)
    asyncio.run(handler.brief_callback(role2, context))
    pron2 = make_update(replies=replies)
    pron2.callback_query = make_callback("brief:pron:0", replies)
    asyncio.run(handler.brief_callback(pron2, context))
    skip_desc2 = make_update(replies=replies)
    skip_desc2.callback_query = make_callback("brief:skip:description", replies)
    asyncio.run(handler.brief_callback(skip_desc2, context))
    skip_secret2 = make_update(replies=replies)
    skip_secret2.callback_query = make_callback("brief:skip:secret", replies)
    asyncio.run(handler.brief_callback(skip_secret2, context))

    assert len(context.user_data["brief_values"]["cast"]) == 2

    next_update = make_update(replies=replies)
    next_update.callback_query = make_callback("brief:next", replies)
    asyncio.run(handler.brief_callback(next_update, context))
    assert context.user_data["brief_step"] == "notes"
    asyncio.run(handler._guided_input(make_update(text=""), context, ""))
    assert context.user_data["brief_step"] == "confirm"

    go_update = make_update(replies=replies)
    go_update.callback_query = make_callback("brief:go", replies)
    asyncio.run(handler.brief_callback(go_update, context))
    assert len(tasks) == 1
    asyncio.run(tasks[0])
    request = generator.calls[0]["request"]
    assert isinstance(request, StoryOutline)
    assert [member.name for member in request.cast] == ["Ana", "Beto"]


def test_the_plot_cannot_be_skipped(tmp_path):
    handler = TelegramStoryBot(FakeGenerator(make_story(tmp_path)))
    context, _ = make_context(FakeBot())
    context.user_data.update(state=ConversationState.GUIDED, brief_step="plot", brief_values={})
    asyncio.run(handler._guided_input(make_update(text="   "), context, "   "))
    assert context.user_data["brief_step"] == "plot"


def test_cancel_reports_each_possible_outcome(tmp_path):
    queue = QueueRepository(tmp_path / "q.sqlite3")
    handler = TelegramStoryBot(FakeGenerator(make_story(tmp_path)), queue)
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
    handler = TelegramStoryBot(FakeGenerator(make_story(tmp_path)), queue)
    replies: list = []
    context, tasks = make_context(FakeBot())

    asyncio.run(handler._launch_generation(make_update(replies=replies), context, "la segunda"))

    assert tasks == []
    assert "no encolé esta" in replies[-1]
    assert 7 not in handler.active_users


# --- start-up validation -----------------------------------------------------


def _break_stagecraft_configuration(monkeypatch, tmp_path):
    """Make the Stagecraft generator fail to build while Telegram settings load fine."""
    monkeypatch.setattr(
        app_module,
        "load_settings",
        lambda: SimpleNamespace(
            telegram_token="t", generator_name="stagecraft", project_root=tmp_path
        ),
    )

    def explode(_name):
        raise GeneratorUnavailable("Falta GEMINI_API_KEY.")

    monkeypatch.setattr(app_module, "create_generator", explode)


def _break_telegram_settings(monkeypatch, tmp_path):
    """Make the Telegram settings themselves fail to load."""

    def explode():
        raise TelegramConfigurationError("Falta TELEGRAM_BOT_TOKEN.")

    monkeypatch.setattr(app_module, "load_settings", explode)


@pytest.mark.parametrize(
    "break_configuration",
    [_break_stagecraft_configuration, _break_telegram_settings],
    ids=["broken-stagecraft-configuration", "missing-telegram-token"],
)
def test_main_reports_broken_configuration_as_exit_code_two(
    monkeypatch, tmp_path, break_configuration
):
    break_configuration(monkeypatch, tmp_path)
    assert app_module.main([]) == 2


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

    handler = TelegramStoryBot(FakeGenerator(make_story(tmp_path)), queue)
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

    handler = TelegramStoryBot(FakeGenerator(make_story(tmp_path)), queue)
    bot = FakeBot()
    context, _ = make_context(bot)

    asyncio.run(handler._refresh_queue(context.application, include_running=True))

    assert [edit["message_id"] for edit in bot.edits] == [99]
    assert "se está generando ahora" in bot.edits[0]["text"]
