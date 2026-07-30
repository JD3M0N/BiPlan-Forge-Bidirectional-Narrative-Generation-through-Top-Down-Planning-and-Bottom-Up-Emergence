import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

from asg_telegram.app import TelegramStoryBot, _evaluator_name


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
    assert context.user_data["state"] == "evaluating"
    assert context.user_data["story_directory"] == str(story)
    assert user.id not in handler.active_users
    assert "Coherencia:" in fake_bot.messages[-1]["text"]


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
