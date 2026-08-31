import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

from asg_core import AudioGenerationError
from asg_telegram import delivery as delivery_module
from asg_telegram import generation as generation_module
from asg_telegram.app import TelegramStoryBot, _evaluator_name, build_application
from asg_top_down.errors import ArtifactValidationError
from asg_top_down.progress import PipelineEvent, ProgressUpdate
from telegram.error import BadRequest, TimedOut


class FakeGenerator:
    display_name = "Fake"

    def __init__(self, story_directory: Path):
        self.story_directory = story_directory
        self.prompts = []

    def generate(self, prompt: str) -> Path:
        self.prompts.append(prompt)
        return self.story_directory


class FailingGenerator:
    display_name = "Fake"

    def generate(self, prompt: str):
        error = ArtifactValidationError(
            "No se pudo completar el capítulo 1 «El eco».",
            details={
                "attempts": 3,
                "missing_node_ids": ["node_2"],
                "missing_goals": ["node_2:investigation"],
            },
            recommendations=["Revisa los checkpoints de planificación."],
        )
        error.run_id = "run-seguro"
        raise error


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


def make_story(tmp_path, text="# Historia\n\nContenido"):
    directory = tmp_path / "story"
    directory.mkdir()
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


def test_generation_delivers_messages_document_and_starts_evaluation(tmp_path):
    story = make_story(tmp_path)
    generator = FakeGenerator(story)
    handler = TelegramStoryBot(generator)
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
    assert context.user_data["state"] == "evaluating"
    assert context.user_data["story_directory"] == str(story)
    assert user.id not in handler.active_users
    assert "<b>Coherencia</b>" in fake_bot.messages[-1]["text"]
    assert "1 — Incoherente" in fake_bot.messages[-1]["text"]
    assert "10 — Totalmente coherente" in fake_bot.messages[-1]["text"]


def test_generation_edits_one_progress_message_until_complete(tmp_path):
    story = make_story(tmp_path)

    class ProgressGenerator(FakeGenerator):
        def generate(self, prompt, on_progress=None):
            on_progress(ProgressUpdate(25, "world", "Construyendo el mundo"))
            on_progress(ProgressUpdate(100, "completed", "Historia terminada"))
            return super().generate(prompt)

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


def test_generation_notifies_quality_warning_and_still_starts_evaluation(tmp_path):
    story = make_story(tmp_path)
    (story / "metadata.json").write_text(
        json.dumps({"warnings": ["Se entregó el mejor borrador disponible."]}),
        encoding="utf-8",
    )
    handler = TelegramStoryBot(FakeGenerator(story))
    bot = FakeBot()
    context = SimpleNamespace(bot=bot, user_data={})
    user = SimpleNamespace(id=12, username="ana", full_name="Ana")

    asyncio.run(
        handler._generate_and_deliver(
            context=context,
            chat_id=20,
            user=user,
            prompt="Una historia",
        )
    )

    assert any("mejor borrador" in message["text"] for message in bot.messages)
    assert context.user_data["state"] == "evaluating"
    assert bot.documents


def test_generation_summarizes_structured_revision_warning(tmp_path):
    story = make_story(tmp_path)
    (story / "metadata.json").write_text(
        json.dumps({"warnings": ["[WRITER_REVISION_REJECTED] fallback"]}),
        encoding="utf-8",
    )
    (story / "revision_report.json").write_text(
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
                                    "code": "WORD_COUNT_OUT_OF_RANGE",
                                    "actual_words": 499,
                                    "minimum_words": 675,
                                    "maximum_words": 900,
                                },
                            },
                            {
                                "status": "rejected",
                                "diagnostic": {
                                    "code": "WORD_COUNT_OUT_OF_RANGE",
                                    "actual_words": 550,
                                    "minimum_words": 675,
                                    "maximum_words": 900,
                                },
                            },
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    (story / "length_audit.json").write_text(
        json.dumps(
            {
                "total": {
                    "actual_words": 1295,
                    "minimum_words": 1350,
                    "target_words": 1500,
                    "within_tolerance": False,
                }
            }
        ),
        encoding="utf-8",
    )
    handler = TelegramStoryBot(FakeGenerator(story))
    bot = FakeBot()
    context = SimpleNamespace(bot=bot, user_data={})
    user = SimpleNamespace(id=12, username="ana", full_name="Ana")

    asyncio.run(
        handler._generate_and_deliver(
            context=context,
            chat_id=20,
            user=user,
            prompt="Una historia",
        )
    )

    warning = next(message["text"] for message in bot.messages if "Código:" in message["text"])
    assert "499 y 550 palabras" in warning
    assert "borrador de 470 palabras" in warning
    assert "Longitud final: 1295 palabras" in warning
    assert "mínimo esperado 1350" in warning


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


def test_active_users_are_isolated(tmp_path):
    handler = TelegramStoryBot(FakeGenerator(make_story(tmp_path)))
    handler.active_users.add(1)
    assert 1 in handler.active_users
    assert 2 not in handler.active_users


def test_evaluator_contains_stable_id_and_readable_name():
    user = SimpleNamespace(id=123, username="lectora", full_name="Ana Pérez")
    assert _evaluator_name(user) == "telegram:123 (lectora)"


def test_completed_scores_are_compatible_with_evaluation_storage(tmp_path):
    from asg_evaluation import METRICS, add_evaluation

    story = make_story(tmp_path)
    scores = dict.fromkeys(METRICS, 8)
    add_evaluation(story, "telegram:123 (lectora)", scores)
    document = json.loads((story / "evaluation.json").read_text(encoding="utf-8"))
    assert document["evaluations"][0] == {
        "user": "telegram:123 (lectora)",
        **scores,
    }


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


def test_document_retries_temporary_network_errors(tmp_path, monkeypatch):
    story = make_story(tmp_path)
    handler = TelegramStoryBot(FakeGenerator(story))
    bot = RetryingDocumentBot([TimedOut(), TimedOut()])
    context = SimpleNamespace(bot=bot, user_data={})
    user = SimpleNamespace(id=1, username="ana", full_name="Ana")
    monkeypatch.setattr(delivery_module, "DOCUMENT_RETRY_DELAYS", (0, 0, 0))

    delivered = asyncio.run(
        handler._send_document_with_retry(
            context=context,
            chat_id=2,
            user=user,
            story_path=story / "story.md",
        )
    )

    assert delivered
    assert bot.document_attempts == 3
    assert len(bot.documents) == 1


def test_document_stops_after_three_failed_retries(tmp_path, monkeypatch):
    story = make_story(tmp_path)
    handler = TelegramStoryBot(FakeGenerator(story))
    bot = RetryingDocumentBot([TimedOut()] * 4)
    context = SimpleNamespace(bot=bot, user_data={})
    user = SimpleNamespace(id=1, username="ana", full_name="Ana")
    monkeypatch.setattr(delivery_module, "DOCUMENT_RETRY_DELAYS", (0, 0, 0))

    delivered = asyncio.run(
        handler._send_document_with_retry(
            context=context,
            chat_id=2,
            user=user,
            story_path=story / "story.md",
        )
    )

    assert not delivered
    assert bot.document_attempts == 4


def test_permanent_document_error_is_not_retried(tmp_path):
    story = make_story(tmp_path)
    handler = TelegramStoryBot(FakeGenerator(story))
    bot = RetryingDocumentBot([BadRequest("archivo rechazado")])
    context = SimpleNamespace(bot=bot, user_data={})
    user = SimpleNamespace(id=1, username="ana", full_name="Ana")

    delivered = asyncio.run(
        handler._send_document_with_retry(
            context=context,
            chat_id=2,
            user=user,
            story_path=story / "story.md",
        )
    )

    assert not delivered
    assert bot.document_attempts == 1


def test_audio_retries_temporary_network_errors(tmp_path, monkeypatch):
    story = make_story(tmp_path)
    handler = TelegramStoryBot(FakeGenerator(story))
    bot = RetryingAudioBot([TimedOut(), TimedOut()])
    context = SimpleNamespace(bot=bot, user_data={})
    user = SimpleNamespace(id=1, username="ana", full_name="Ana")
    monkeypatch.setattr(delivery_module, "AUDIO_RETRY_DELAYS", (0, 0, 0))

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


def test_audio_rejection_does_not_block_evaluation(tmp_path):
    story = make_story(tmp_path)
    handler = TelegramStoryBot(FakeGenerator(story))
    bot = RetryingAudioBot([BadRequest("audio rechazado")])
    context = SimpleNamespace(bot=bot, user_data={})
    user = SimpleNamespace(id=1, username="ana", full_name="Ana")

    asyncio.run(
        handler._generate_and_deliver(
            context=context,
            chat_id=2,
            user=user,
            prompt="Historia",
        )
    )

    assert bot.audio_attempts == 1
    assert any("Telegram no pudo recibir el MP3" in message["text"] for message in bot.messages)
    assert context.user_data["state"] == "evaluating"


def test_audio_generation_failure_does_not_block_evaluation(tmp_path, monkeypatch):
    story = make_story(tmp_path)
    (story / "story.mp3").unlink()
    (story / "audio.json").unlink()

    async def fail_audio(story_path):
        raise AudioGenerationError("tts unavailable")

    monkeypatch.setattr(delivery_module, "create_story_audio", fail_audio)
    handler = TelegramStoryBot(FakeGenerator(story))
    bot = FakeBot()
    context = SimpleNamespace(bot=bot, user_data={})
    user = SimpleNamespace(id=1, username="ana", full_name="Ana")

    asyncio.run(
        handler._generate_and_deliver(
            context=context,
            chat_id=2,
            user=user,
            prompt="Historia",
        )
    )

    assert not bot.audios
    assert any("no pude crear su audio" in message["text"] for message in bot.messages)
    assert context.user_data["state"] == "evaluating"


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
    assert first.user_data["state"] == "evaluating"
    assert second.user_data["state"] == "evaluating"


def test_application_uses_resilient_timeouts():
    application = build_application(
        "123456:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghi",
        TelegramStoryBot(SimpleNamespace(display_name="Fake")),
    )
    request = application.bot.request
    timeout = request._client_kwargs["timeout"]
    assert timeout.connect == 15
    assert timeout.read == 30
    assert timeout.write == 30
    assert timeout.pool == 10
    assert request._media_write_timeout == 60


def test_pipeline_events_are_logged_without_editing_chat(tmp_path, monkeypatch):
    story = make_story(tmp_path)
    actions = []

    class EventGenerator(FakeGenerator):
        def generate(self, prompt, on_progress=None, on_event=None):
            on_event(PipelineEvent("agent_called", "se llamo al agente planner"))
            return super().generate(prompt)

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
