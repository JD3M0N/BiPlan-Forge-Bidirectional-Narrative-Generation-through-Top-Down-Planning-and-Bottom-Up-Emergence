import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from asg_core import AudioGenerationError
from asg_telegram import delivery as delivery_module
from asg_telegram import generation as generation_module
from asg_telegram.app import TelegramStoryBot, _evaluator_name
from asg_telegram.contract import (
    GenerationEvent,
    GenerationFailure,
    GenerationProgress,
    ProfileOption,
)
from asg_telegram.generators import summarize_run
from telegram.error import BadRequest, TimedOut

PROFILES = (
    ProfileOption("essential", "Esencial", ("essential", "esencial")),
    ProfileOption("developed", "Desarrollada", ("developed", "desarrollada")),
    ProfileOption("expansive", "Expansiva", ("expansive", "expansiva")),
)


class FakeGenerator:
    """A generator double bound to the same contract the real adapter honours."""

    display_name = "Fake"
    profiles = PROFILES

    def __init__(self, story_directory: Path):
        self.story_directory = story_directory
        self.prompts = []
        self.requested_profiles = []

    def generate(
        self,
        prompt: str,
        *,
        narrative_profile=None,
        on_progress=None,
        on_run_created=None,
        on_event=None,
    ) -> Path:
        self.prompts.append(prompt)
        self.requested_profiles.append(narrative_profile)
        self._report(on_progress, on_event)
        if on_run_created is not None:
            on_run_created(self.story_directory)
        return self.story_directory

    def _report(self, on_progress, on_event):
        """Emit whatever progress and events this double is configured with."""

    def summarize(self, run_dir: Path):
        return summarize_run(run_dir)


class FailingGenerator(FakeGenerator):
    display_name = "Fake"
    profiles = PROFILES

    def __init__(self):
        super().__init__(Path("."))

    def generate(self, prompt: str, **kwargs):
        raise GenerationFailure(
            "No se pudo completar el capítulo 1 «El eco».",
            code="ARTIFACT_VALIDATION_FAILED",
            stage="planning",
            recommendation="Revisa los checkpoints de planificación.",
            run_id="run-seguro",
        )


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


def test_generation_edits_one_progress_message_until_complete(tmp_path):
    story = make_story(tmp_path)

    class ProgressGenerator(FakeGenerator):
        def _report(self, on_progress, on_event):
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
        def _report(self, on_progress, on_event):
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


def test_generation_reports_quality_warnings_and_still_evaluates(tmp_path):
    """A plain metadata warning and a structured revision-report warning both reach the user."""
    simple = make_story(tmp_path / "simple")
    (simple / "metadata.json").write_text(
        json.dumps({"warnings": ["Se entregó el mejor borrador disponible."]}),
        encoding="utf-8",
    )
    handler = TelegramStoryBot(FakeGenerator(simple))
    bot = FakeBot()
    context = SimpleNamespace(bot=bot, user_data={})
    user = SimpleNamespace(id=12, username="ana", full_name="Ana")
    asyncio.run(
        handler._generate_and_deliver(context=context, chat_id=20, user=user, prompt="Historia")
    )
    assert any("mejor borrador" in message["text"] for message in bot.messages)
    assert context.user_data["state"] == "evaluating"
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
    (structured / "length_audit.json").write_text(
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
    handler = TelegramStoryBot(FakeGenerator(structured))
    bot = FakeBot()
    context = SimpleNamespace(bot=bot, user_data={})
    asyncio.run(
        handler._generate_and_deliver(context=context, chat_id=20, user=user, prompt="Historia")
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


def test_evaluation_is_stored_under_a_stable_evaluator_id(tmp_path):
    """The evaluator id shown to the user is exactly what evaluation storage persists."""
    from asg_evaluation import METRICS, add_evaluation

    user = SimpleNamespace(id=123, username="lectora", full_name="Ana Pérez")
    evaluator = _evaluator_name(user)
    assert evaluator == "telegram:123 (lectora)"

    story = make_story(tmp_path)
    scores = dict.fromkeys(METRICS, 8)
    add_evaluation(story, evaluator, scores)
    document = json.loads((story / "evaluation.json").read_text(encoding="utf-8"))
    assert document["evaluations"][0] == {"user": evaluator, **scores}


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


def test_audio_failure_never_blocks_evaluation_regardless_of_cause(tmp_path, monkeypatch):
    """A rejected audio and a failed audio generation both still let the user evaluate."""
    rejected = make_story(tmp_path / "rejected")
    handler = TelegramStoryBot(FakeGenerator(rejected))
    bot = RetryingAudioBot([BadRequest("audio rechazado")])
    context = SimpleNamespace(bot=bot, user_data={})
    user = SimpleNamespace(id=1, username="ana", full_name="Ana")
    asyncio.run(
        handler._generate_and_deliver(context=context, chat_id=2, user=user, prompt="Historia")
    )
    assert bot.audio_attempts == 1
    assert any("Telegram no pudo recibir el MP3" in message["text"] for message in bot.messages)
    assert context.user_data["state"] == "evaluating"

    failed = make_story(tmp_path / "failed")
    (failed / "story.mp3").unlink()
    (failed / "audio.json").unlink()

    async def fail_audio(story_path):
        raise AudioGenerationError("tts unavailable")

    monkeypatch.setattr(delivery_module, "create_story_audio", fail_audio)
    handler = TelegramStoryBot(FakeGenerator(failed))
    bot = FakeBot()
    context = SimpleNamespace(bot=bot, user_data={})
    asyncio.run(
        handler._generate_and_deliver(context=context, chat_id=2, user=user, prompt="Historia")
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


def test_pipeline_events_are_logged_without_editing_chat(tmp_path, monkeypatch):
    story = make_story(tmp_path)
    actions = []

    class EventGenerator(FakeGenerator):
        def _report(self, on_progress, on_event):
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
