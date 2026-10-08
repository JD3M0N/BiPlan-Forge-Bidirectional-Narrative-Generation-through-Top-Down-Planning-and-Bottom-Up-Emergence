import asyncio
import json
from types import SimpleNamespace

import pytest
from asg_core import AudioGenerationError
from asg_telegram import delivery as delivery_module
from asg_telegram import generation as generation_module
from asg_telegram.contract import GenerationEvent, GenerationProgress
from asg_telegram.handlers import TelegramStoryBot
from telegram.error import BadRequest, TimedOut
from telegram_fakes import FailingGenerator, FakeGenerator


class FakeBot:
    def __init__(self):
        self.messages = []
        self.documents = []
        self.audios = []
        self.edits = []
        self.events = []

    async def send_message(self, **kwargs):
        self.messages.append(kwargs)
        if kwargs.get("parse_mode") == "HTML":
            self.events.append("fragment")

    async def send_document(self, **kwargs):
        self.events.append("document")
        self.documents.append(
            {
                **kwargs,
                "content": kwargs["document"].read().decode("utf-8"),
            }
        )

    async def send_audio(self, **kwargs):
        self.events.append("audio")
        self.audios.append(
            {
                **kwargs,
                "content": kwargs["audio"].read(),
            }
        )

    async def edit_message_text(self, **kwargs):
        self.edits.append(kwargs)


def spy_after_delivery(handler) -> list:
    """Record each user whose delivery reached its final step."""
    finished = []

    async def after_delivery(context, chat_id, user, enrolled):
        """Append the user instead of guiding them."""
        finished.append(user.id)

    handler._after_delivery = after_delivery
    return finished


def make_story(tmp_path, text="# Historia\n\nContenido"):
    directory = tmp_path / "story"
    directory.mkdir(parents=True)
    (directory / "story.md").write_text(text, encoding="utf-8")
    (directory / "story.mp3").write_bytes(b"fake-mp3")
    (directory / "audio.json").write_text(
        json.dumps(
            {
                "status": "completed",
                "language": "es",
                "voice": "es-MX-FakeNeural",
            }
        ),
        encoding="utf-8",
    )
    return directory


def test_generation_delivers_messages_document_and_finishes(tmp_path):
    story = make_story(tmp_path)
    generator = FakeGenerator(story)
    handler = TelegramStoryBot(generator)
    finished = spy_after_delivery(handler)
    fake_bot = FakeBot()
    context = SimpleNamespace(bot=fake_bot, user_data={})
    user = SimpleNamespace(id=10, username="ana", full_name="Ana")
    handler.active_users.add(user.id)

    asyncio.run(
        handler._generate_and_deliver(
            context=context,
            chat_id=20,
            user=user,
            prompt="Una historia",
        )
    )

    assert generator.prompts == ["Una historia"]
    assert fake_bot.documents[0]["content"] == (story / "story.md").read_bytes().decode("utf-8")
    assert fake_bot.audios[0]["content"] == b"fake-mp3"
    assert fake_bot.audios[0]["title"] == "Historia"
    assert fake_bot.events[:3] == ["document", "audio", "fragment"]
    assert (story / "story.md").read_text(encoding="utf-8") == ("# Historia\n\nContenido")
    assert fake_bot.messages[0]["parse_mode"] == "HTML"
    assert finished == [user.id]
    assert user.id not in handler.active_users


def test_generation_edits_one_progress_message_until_complete(tmp_path):
    story = make_story(tmp_path)

    class ProgressGenerator(FakeGenerator):
        def _report(self, on_progress, on_event, should_cancel):
            on_progress(GenerationProgress(25, "world", "Construyendo el mundo"))
            on_progress(GenerationProgress(100, "completed", "Historia terminada"))

    handler = TelegramStoryBot(ProgressGenerator(story))
    bot = FakeBot()
    context = SimpleNamespace(bot=bot, user_data={})
    user = SimpleNamespace(id=11, username="ana", full_name="Ana")

    asyncio.run(
        handler._generate_and_deliver(
            context=context,
            chat_id=20,
            user=user,
            prompt="Una historia",
            progress_message_id=99,
        )
    )

    assert len(bot.edits) == 2
    assert {edit["message_id"] for edit in bot.edits} == {99}
    assert "100% — Historia terminada" in bot.edits[-1]["text"]


def test_generation_is_not_blocked_by_a_hanging_progress_edit(tmp_path):
    story = make_story(tmp_path)

    class ProgressGenerator(FakeGenerator):
        def _report(self, on_progress, on_event, should_cancel):
            on_progress(GenerationProgress(25, "world", "Construyendo el mundo"))

    class HangingBot(FakeBot):
        async def edit_message_text(self, **kwargs):
            await asyncio.sleep(999)

    handler = TelegramStoryBot(ProgressGenerator(story))
    handler.PROGRESS_EDIT_TIMEOUT = 0.05
    bot = HangingBot()
    context = SimpleNamespace(bot=bot, user_data={})
    user = SimpleNamespace(id=12, username="ana", full_name="Ana")

    asyncio.run(
        asyncio.wait_for(
            handler._generate_and_deliver(
                context=context,
                chat_id=20,
                user=user,
                prompt="Una historia",
                progress_message_id=99,
            ),
            timeout=5,
        )
    )

    assert bot.documents


def test_generation_reports_quality_warnings_and_still_finishes(tmp_path):
    """A plain metadata warning and a structured revision-report warning both reach the user."""
    simple = make_story(tmp_path / "simple")
    (simple / "metadata.json").write_text(
        json.dumps({"warnings": ["Se entregó el mejor borrador disponible."]}),
        encoding="utf-8",
    )
    handler = TelegramStoryBot(FakeGenerator(simple))
    finished = spy_after_delivery(handler)
    bot = FakeBot()
    context = SimpleNamespace(bot=bot, user_data={})
    user = SimpleNamespace(id=12, username="ana", full_name="Ana")
    asyncio.run(
        handler._generate_and_deliver(context=context, chat_id=20, user=user, prompt="Historia")
    )
    assert any("mejor borrador" in message["text"] for message in bot.messages)
    assert finished == [user.id]
    assert bot.documents

    structured = make_story(tmp_path / "structured")
    (structured / "metadata.json").write_text(
        json.dumps({"warnings": ["[WRITER_REVISION_REJECTED] fallback"]}),
        encoding="utf-8",
    )
    (structured / "revision_report.json").write_text(
        json.dumps(
            {
                "chapters": [
                    {
                        "chapter_index": 1,
                        "draft_words": 470,
                        "warning_code": "WRITER_REVISION_REJECTED",
                        "attempts": [
                            {
                                "status": "rejected",
                                "diagnostic": {
                                    "code": "UNCHANGED_SIGNIFICANT_NOTES",
                                    "actual_words": 470,
                                },
                            },
                            {"status": "failed", "exception_type": "TimeoutError"},
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    handler = TelegramStoryBot(FakeGenerator(structured))
    bot = FakeBot()
    context = SimpleNamespace(bot=bot, user_data={})
    asyncio.run(
        handler._generate_and_deliver(context=context, chat_id=20, user=user, prompt="Historia")
    )
    warning = next(message["text"] for message in bot.messages if "Código:" in message["text"])
    assert "Capítulo 1: no hubo una revisión válida" in warning
    assert "(UNCHANGED_SIGNIFICANT_NOTES, TimeoutError)" in warning
    assert "borrador de 470 palabras" in warning


def test_generation_reports_actionable_safe_error() -> None:
    handler = TelegramStoryBot(FailingGenerator())
    bot = FakeBot()
    context = SimpleNamespace(bot=bot, user_data={})
    user = SimpleNamespace(id=11, username="ana", full_name="Ana")

    asyncio.run(
        handler._generate_and_deliver(
            context=context,
            chat_id=20,
            user=user,
            prompt="Historia",
            progress_message_id=99,
        )
    )

    notice = bot.messages[-1]["text"]
    assert "ARTIFACT_VALIDATION_FAILED" in notice
    assert "checkpoints" in notice
    assert "run-seguro" in notice
    assert "GEMINI_API_KEY" not in notice
    assert "planning:" in bot.edits[-1]["text"]


class RetryingDocumentBot(FakeBot):
    def __init__(self, failures):
        super().__init__()
        self.failures = list(failures)
        self.document_attempts = 0

    async def send_document(self, **kwargs):
        self.document_attempts += 1
        if self.failures:
            raise self.failures.pop(0)
        await super().send_document(**kwargs)


class RetryingAudioBot(FakeBot):
    def __init__(self, failures):
        super().__init__()
        self.failures = list(failures)
        self.audio_attempts = 0

    async def send_audio(self, **kwargs):
        self.audio_attempts += 1
        if self.failures:
            raise self.failures.pop(0)
        await super().send_audio(**kwargs)


@pytest.mark.parametrize(
    ("failures", "expect_delivered", "expected_attempts"),
    [
        ([TimedOut(), TimedOut()], True, 3),
        ([TimedOut()] * 4, False, 4),
        ([BadRequest("archivo rechazado")], False, 1),
    ],
    ids=[
        "temporary-errors-eventually-succeed",
        "exhausts-after-three-retries",
        "permanent-error-is-not-retried",
    ],
)
def test_delivery_retries_only_temporary_errors(
    tmp_path, monkeypatch, failures, expect_delivered, expected_attempts
):
    """`BadRequest` must be checked before `NetworkError` in the handler, or this misclassifies."""
    story = make_story(tmp_path)
    handler = TelegramStoryBot(FakeGenerator(story))
    bot = RetryingDocumentBot(failures)
    context = SimpleNamespace(bot=bot, user_data={})
    user = SimpleNamespace(id=1, username="ana", full_name="Ana")
    monkeypatch.setattr(delivery_module, "RETRY_DELAYS", (0, 0, 0))

    delivered = asyncio.run(
        handler._send_document_with_retry(
            context=context,
            chat_id=2,
            user=user,
            story_path=story / "story.md",
        )
    )

    assert delivered is expect_delivered
    assert bot.document_attempts == expected_attempts


def test_audio_retries_temporary_network_errors(tmp_path, monkeypatch):
    story = make_story(tmp_path)
    handler = TelegramStoryBot(FakeGenerator(story))
    bot = RetryingAudioBot([TimedOut(), TimedOut()])
    context = SimpleNamespace(bot=bot, user_data={})
    user = SimpleNamespace(id=1, username="ana", full_name="Ana")
    monkeypatch.setattr(delivery_module, "RETRY_DELAYS", (0, 0, 0))

    delivered = asyncio.run(
        handler._deliver_audio(
            context=context,
            chat_id=2,
            user=user,
            story_path=story / "story.md",
            story=(story / "story.md").read_text(encoding="utf-8"),
        )
    )

    assert delivered
    assert bot.audio_attempts == 3
    assert bot.audios[0]["content"] == b"fake-mp3"


def test_chosen_voice_is_passed_to_audio_creation(tmp_path, monkeypatch):
    story = make_story(tmp_path)
    handler = TelegramStoryBot(FakeGenerator(story))
    bot = FakeBot()
    context = SimpleNamespace(bot=bot, user_data={})
    user = SimpleNamespace(id=1, username="ana", full_name="Ana")
    calls = []

    async def create(story_path, **kwargs):
        calls.append(kwargs)
        path = story_path.with_suffix(".mp3")
        return SimpleNamespace(path=path, language="es", voice=kwargs["voice"])

    (story / "story.mp3").write_bytes(b"fake-mp3")
    monkeypatch.setattr(delivery_module, "create_story_audio", create)

    asyncio.run(
        handler._deliver_audio(
            context=context,
            chat_id=2,
            user=user,
            story_path=story / "story.md",
            story="texto",
            voice="es-CU-BelkysNeural",
        )
    )
    assert calls == [{"voice": "es-CU-BelkysNeural"}]


def test_audio_is_skipped_when_the_run_had_it_off(tmp_path):
    story = make_story(tmp_path)
    handler = TelegramStoryBot(FakeGenerator(story))
    bot = FakeBot()
    context = SimpleNamespace(bot=bot, user_data={})
    user = SimpleNamespace(id=1, username="ana", full_name="Ana")

    delivered = asyncio.run(
        handler._deliver_story(
            context=context,
            chat_id=2,
            user=user,
            story_path=story / "story.md",
            audio=False,
        )
    )

    assert delivered
    assert bot.audios == []


def test_audio_failure_never_blocks_delivery_regardless_of_cause(tmp_path, monkeypatch):
    """A rejected audio and a failed audio generation both still finish the delivery."""
    rejected = make_story(tmp_path / "rejected")
    handler = TelegramStoryBot(FakeGenerator(rejected))
    finished = spy_after_delivery(handler)
    bot = RetryingAudioBot([BadRequest("audio rechazado")])
    context = SimpleNamespace(bot=bot, user_data={})
    user = SimpleNamespace(id=1, username="ana", full_name="Ana")
    asyncio.run(
        handler._generate_and_deliver(context=context, chat_id=2, user=user, prompt="Historia")
    )
    assert bot.audio_attempts == 1
    assert any("Telegram no pudo recibir el MP3" in message["text"] for message in bot.messages)
    assert finished == [user.id]

    failed = make_story(tmp_path / "failed")
    (failed / "story.mp3").unlink()
    (failed / "audio.json").unlink()

    async def fail_audio(story_path):
        raise AudioGenerationError("tts unavailable")

    monkeypatch.setattr(delivery_module, "create_story_audio", fail_audio)
    handler = TelegramStoryBot(FakeGenerator(failed))
    finished = spy_after_delivery(handler)
    bot = FakeBot()
    context = SimpleNamespace(bot=bot, user_data={})
    asyncio.run(
        handler._generate_and_deliver(context=context, chat_id=2, user=user, prompt="Historia")
    )
    assert not bot.audios
    assert any("no pude crear su audio" in message["text"] for message in bot.messages)
    assert finished == [user.id]


class FragmentTimeoutBot(FakeBot):
    def __init__(self):
        super().__init__()
        self.fragment_attempts = 0

    async def send_message(self, **kwargs):
        if kwargs.get("parse_mode") == "HTML":
            self.fragment_attempts += 1
            raise TimedOut()
        await super().send_message(**kwargs)


def test_fragment_timeout_falls_back_to_file_without_retry(tmp_path):
    story = make_story(tmp_path, "# Historia\n\n" + ("contenido " * 1000))
    handler = TelegramStoryBot(FakeGenerator(story))
    bot = FragmentTimeoutBot()
    context = SimpleNamespace(bot=bot, user_data={})
    user = SimpleNamespace(id=1, username="ana", full_name="Ana")

    delivered = asyncio.run(
        handler._deliver_story(
            context=context,
            chat_id=2,
            user=user,
            story_path=story / "story.md",
        )
    )

    assert delivered
    assert len(bot.documents) == 1
    assert bot.fragment_attempts == 1
    assert any("archivo completo" in message["text"] for message in bot.messages)


def test_deliveries_are_serialized_between_users(tmp_path):
    story = make_story(tmp_path)
    handler = TelegramStoryBot(FakeGenerator(story))
    finished = spy_after_delivery(handler)
    active = 0
    maximum = 0

    async def tracked_delivery(**kwargs):
        nonlocal active, maximum
        active += 1
        maximum = max(maximum, active)
        await asyncio.sleep(0)
        active -= 1
        return True

    handler._deliver_story = tracked_delivery
    first = SimpleNamespace(bot=FakeBot(), user_data={})
    second = SimpleNamespace(bot=FakeBot(), user_data={})
    users = [
        SimpleNamespace(id=1, username="uno", full_name="Uno"),
        SimpleNamespace(id=2, username="dos", full_name="Dos"),
    ]

    async def run_both():
        await asyncio.gather(
            handler._generate_and_deliver(context=first, chat_id=1, user=users[0], prompt="uno"),
            handler._generate_and_deliver(context=second, chat_id=2, user=users[1], prompt="dos"),
        )

    asyncio.run(run_both())
    assert maximum == 1
    assert sorted(finished) == [1, 2]


def test_pipeline_events_are_logged_without_editing_chat(tmp_path, monkeypatch):
    story = make_story(tmp_path)
    actions = []

    class EventGenerator(FakeGenerator):
        def _report(self, on_progress, on_event, should_cancel):
            on_event(GenerationEvent("se llamo al agente planner", "planning"))

    monkeypatch.setattr(
        generation_module,
        "log_user_action",
        lambda logger, **kwargs: actions.append(kwargs["action"]),
    )
    handler = TelegramStoryBot(EventGenerator(story))
    bot = FakeBot()
    context = SimpleNamespace(bot=bot, user_data={})
    user = SimpleNamespace(id=11, username="ana", full_name="Ana")
    asyncio.run(
        handler._generate_and_deliver(
            context=context,
            chat_id=20,
            user=user,
            prompt="Una historia",
            progress_message_id=99,
        )
    )
    assert "se llamo al agente planner" in actions
    assert bot.edits == []


def test_artifact_events_stay_out_of_the_info_log(tmp_path, monkeypatch):
    story = make_story(tmp_path)
    levels = []

    class EventGenerator(FakeGenerator):
        def _report(self, on_progress, on_event, should_cancel):
            on_event(GenerationEvent("artefacto creado", "writing", "artifact_created"))

    monkeypatch.setattr(
        generation_module,
        "log_user_action",
        lambda logger, **kwargs: levels.append(kwargs.get("level")),
    )
    handler = TelegramStoryBot(EventGenerator(story))
    bot = FakeBot()
    context = SimpleNamespace(bot=bot, user_data={})
    user = SimpleNamespace(id=11, username="ana", full_name="Ana")
    asyncio.run(
        handler._generate_and_deliver(context=context, chat_id=20, user=user, prompt="Una historia")
    )
    import logging

    assert logging.DEBUG in levels
