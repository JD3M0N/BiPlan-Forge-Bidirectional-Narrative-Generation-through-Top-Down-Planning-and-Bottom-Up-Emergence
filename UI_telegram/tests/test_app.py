import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

from telegram.error import BadRequest, TimedOut

from asg_telegram import app
from asg_telegram.app import TelegramStoryBot, _evaluator_name, build_application


class FakeGenerator:
    display_name = "Fake"

    def __init__(self, story_directory: Path):
        self.story_directory = story_directory
        self.prompts = []

    def generate(self, prompt: str) -> Path:
        self.prompts.append(prompt)
        return self.story_directory


class FakeBot:
    def __init__(self):
        self.messages = []
        self.documents = []

    async def send_message(self, **kwargs):
        self.messages.append(kwargs)

    async def send_document(self, **kwargs):
        self.documents.append(
            {
                **kwargs,
                "content": kwargs["document"].read().decode("utf-8"),
            }
        )


def make_story(tmp_path, text="# Historia\n\nContenido"):
    directory = tmp_path / "story"
    directory.mkdir()
    (directory / "story.md").write_text(text, encoding="utf-8")
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
    assert fake_bot.documents[0]["content"] == (
        story / "story.md"
    ).read_bytes().decode("utf-8")
    assert (story / "story.md").read_text(encoding="utf-8") == (
        "# Historia\n\nContenido"
    )
    assert fake_bot.messages[0]["parse_mode"] == "HTML"
    assert context.user_data["state"] == "evaluating"
    assert context.user_data["story_directory"] == str(story)
    assert user.id not in handler.active_users
    assert "<b>Coherencia</b>" in fake_bot.messages[-1]["text"]
    assert "1 — Incoherente" in fake_bot.messages[-1]["text"]
    assert "10 — Totalmente coherente" in fake_bot.messages[-1]["text"]


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
    document = json.loads(
        (story / "evaluation.json").read_text(encoding="utf-8")
    )
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


def test_document_retries_temporary_network_errors(tmp_path, monkeypatch):
    story = make_story(tmp_path)
    handler = TelegramStoryBot(FakeGenerator(story))
    bot = RetryingDocumentBot([TimedOut(), TimedOut()])
    context = SimpleNamespace(bot=bot, user_data={})
    user = SimpleNamespace(id=1, username="ana", full_name="Ana")
    monkeypatch.setattr(app, "DOCUMENT_RETRY_DELAYS", (0, 0, 0))

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
    monkeypatch.setattr(app, "DOCUMENT_RETRY_DELAYS", (0, 0, 0))

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
            handler._generate_and_deliver(
                context=first, chat_id=1, user=users[0], prompt="uno"
            ),
            handler._generate_and_deliver(
                context=second, chat_id=2, user=users[1], prompt="dos"
            ),
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
