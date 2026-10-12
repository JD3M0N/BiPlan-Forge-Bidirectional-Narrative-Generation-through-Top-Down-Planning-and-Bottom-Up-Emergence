"""Offline doubles for the bot: a recording Telegram bot, chats and a fake generator."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from asg_telegram.generator import GenerationFailure


class FakeMessage:
    """A sent message whose edits are recorded."""

    def __init__(self, bot, **sent) -> None:
        """Remember what was sent and where."""
        self.bot = bot
        self.sent = sent
        self.chat = SimpleNamespace(id=sent.get("chat_id"))

    async def edit_text(self, text, **kwargs):
        """Record an edit of this message."""
        self.bot.edits.append(text)

    async def reply_text(self, text, **kwargs):
        """Reply in the same chat."""
        return await self.bot.send_message(chat_id=self.chat.id, text=text, **kwargs)


class FakeBot:
    """Record every outgoing call instead of talking to Telegram."""

    def __init__(self) -> None:
        """Start with empty logs."""
        self.messages: list[dict] = []
        self.documents: list[dict] = []
        self.audios: list[dict] = []
        self.edits: list[str] = []

    async def send_message(self, **kwargs):
        """Record a text message."""
        self.messages.append(kwargs)
        return FakeMessage(self, **kwargs)

    async def send_document(self, **kwargs):
        """Record a document upload."""
        self.documents.append(kwargs)

    async def send_audio(self, **kwargs):
        """Record an audio upload."""
        self.audios.append(kwargs)

    def texts(self) -> list[str]:
        """Return every message text, in order."""
        return [m["text"] for m in self.messages]

    def buttons(self) -> list[str]:
        """Return the callback data of the last message that carried a keyboard."""
        markup = next(m["reply_markup"] for m in reversed(self.messages) if m.get("reply_markup"))
        return [button.callback_data for row in markup.inline_keyboard for button in row]


class Chat:
    """One participant talking to the bot: builds updates and a shared context."""

    def __init__(self, bot: FakeBot, user_id: int = 7) -> None:
        """Bind the participant to the recording bot."""
        self.bot = bot
        self.user = SimpleNamespace(id=user_id, username=f"user{user_id}", full_name="Persona")
        self.chat = SimpleNamespace(id=user_id)
        self.context = SimpleNamespace(user_data={}, bot=bot)

    def message(self, text: str = "/start"):
        """Build an update carrying a text message."""
        message = FakeMessage(self.bot, chat_id=self.chat.id)
        message.text = text
        return SimpleNamespace(
            effective_user=self.user, effective_chat=self.chat, effective_message=message
        )

    def press(self, data: str):
        """Build an update carrying a button press."""
        bot = self.bot

        async def answer(text=None, show_alert=False):
            """Record the toast shown for the press."""
            bot.edits.append(f"toast:{text}")

        async def edit_message_text(text, reply_markup=None, **kwargs):
            """Record the message rewritten in place."""
            await bot.send_message(chat_id=self.chat.id, text=text, reply_markup=reply_markup)

        async def edit_message_reply_markup(reply_markup=None):
            """Record the keyboard being removed."""

        query = SimpleNamespace(
            data=data,
            from_user=self.user,
            message=SimpleNamespace(chat=self.chat),
            answer=answer,
            edit_message_text=edit_message_text,
            edit_message_reply_markup=edit_message_reply_markup,
        )
        return SimpleNamespace(
            callback_query=query,
            effective_user=self.user,
            effective_chat=self.chat,
            effective_message=query.message,
        )


def fake_run(root: Path, name: str, story_format: str = "narrative") -> Path:
    """Write a completed prose run with narration, as the study expects."""
    run = root / name
    run.mkdir(parents=True)
    (run / "story.md").write_text(f"# {name}\n\nAda abre la puerta de {name}.", encoding="utf-8")
    (run / "story.mp3").write_bytes(b"ID3")
    for file, data in (
        ("metadata.json", {"status": "completed", "story_format": story_format}),
        ("generation_options.json", {"story_format": story_format}),
        ("generator_version.json", {"generator_version": "test"}),
        ("request.json", {"original_prompt": name}),
    ):
        (run / file).write_text(json.dumps(data), encoding="utf-8")
    return run


class FakeGenerator:
    """Write a fake run per request, or fail on demand."""

    def __init__(self, root: Path, failure: GenerationFailure | None = None) -> None:
        """Keep where runs go and the calls received."""
        self.root = root
        self.failure = failure
        self.calls: list[tuple] = []
        self.closed: list[Path] = []

    def generate(
        self, request, story_format, *, on_progress=None, should_cancel=None, on_run_created=None
    ):
        """Record the call, report progress and return a new run."""
        self.calls.append((request, story_format))
        if on_run_created:
            on_run_created(self.root / f"run-{len(self.calls)}")
        if on_progress:
            on_progress(50, "Escribiendo")
        if self.failure:
            raise self.failure
        return fake_run(self.root, f"run-{len(self.calls)}", story_format)

    def close_interrupted(self, run_dir: Path) -> None:
        """Record the run a restart asked to close."""
        self.closed.append(run_dir)
