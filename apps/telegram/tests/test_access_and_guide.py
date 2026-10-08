"""Shared-key access, the participant journey and phase announcements, without Telegram."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from asg_evaluation.demo import prepare_demo, synthetic_run
from asg_evaluation.study import StudyRepository
from asg_telegram import guide as texts
from asg_telegram.access import MAX_FAILURES, AccessGate
from asg_telegram.announcer import PhaseAnnouncer
from asg_telegram.guide import ParticipantGuide, Step
from asg_telegram.handlers import TelegramStoryBot
from asg_telegram.queue import QueueRepository
from asg_telegram.study import StudyConversation
from telegram.ext import ApplicationHandlerStop
from telegram_fakes import FakeGenerator


def experiment(tmp_path, repository=None):
    """Assemble the bot exactly as main() does, around a study in collection."""
    if repository is None:
        repository = StudyRepository(tmp_path / "study.sqlite3")
        repository.create("piloto", required_version="DEMO-1")
        repository.transition("collection")
    bot = TelegramStoryBot(FakeGenerator(tmp_path), QueueRepository(tmp_path / "q.sqlite3"))
    bot.study = StudyConversation(repository, bot)
    bot.guide = ParticipantGuide(bot)
    return bot


def chat_update(user_id=7, text="", replies=None):
    """Build a private-chat message update that records replies."""
    sent = replies if replies is not None else []

    async def reply_text(text, **kwargs):
        sent.append((text, kwargs))
        return SimpleNamespace(message_id=len(sent))

    return SimpleNamespace(
        effective_user=SimpleNamespace(id=user_id, username="ana", full_name="Ana"),
        effective_chat=SimpleNamespace(id=user_id, type="private"),
        effective_message=SimpleNamespace(text=text, reply_text=reply_text, delete=AsyncMock()),
        callback_query=None,
    )


def buttons(markup) -> list[str]:
    """Flatten a keyboard into its callback payloads."""
    return [button.callback_data for row in markup.inline_keyboard for button in row]


def chat_context():
    """Build a context whose bot records every sent message."""
    return SimpleNamespace(bot=SimpleNamespace(send_message=AsyncMock()), user_data={})


@pytest.mark.parametrize(
    ("phase", "setup", "expected"),
    [
        ("collection", "none", Step.LOCKED),
        ("collection", "key", Step.CONSENT),
        ("preparation", "consent", Step.PROFILE),
        ("preparation", "profile", Step.WAITING),
        ("collection", "profile", Step.BASE_STORY),
        ("collection", "enrolled", Step.READY),
        ("collection", "author", Step.READY),
        ("evaluation", "consent", Step.ENROLLMENT_CLOSED),
        ("evaluation", "profile", Step.READY),
    ],
)
def test_each_step_is_derived_from_durable_state(tmp_path, phase, setup, expected):
    bot = experiment(tmp_path)
    repository = bot.study.repository
    stages = ["none", "key", "consent", "profile", "enrolled"]
    reached = stages.index(setup) if setup in stages else stages.index("profile")
    if reached >= 1:
        bot.queue.grant(7)
    if reached >= 2:
        bot.queue.set_consent(7, True)
    if reached >= 3:
        reader = repository.participant("7", profile="regular", is_author=setup == "author")
    if reached >= 4:
        repository.add_story(synthetic_run(tmp_path / "base", 1), owner=reader["id"])
    with repository.transaction() as db:
        db.execute("UPDATE study SET state=?", (phase,))
    status = bot.guide.status(7)
    assert status.step == expected
    assert status.can_generate == (
        expected in {Step.BASE_STORY, Step.READY, Step.ENROLLMENT_CLOSED}
    )
    text, _ = bot.guide.render(status)
    assert text


def test_base_story_comes_first_and_only_in_prose(tmp_path):
    """Consent and profile unlock the base story; only after it is enrolled is everything open."""
    bot = experiment(tmp_path)
    repository = bot.study.repository
    bot.queue.grant(7)
    context = chat_context()

    replies: list = []
    asyncio.run(bot.settings(chat_update(replies=replies), context))
    assert texts.CONSENT_TEXT in context.bot.send_message.call_args.kwargs["text"]

    for data in ("guide:consent:yes", "guide:profile:regular"):
        query = SimpleNamespace(
            data=data, answer=AsyncMock(), edit_message_reply_markup=AsyncMock()
        )
        update = chat_update()
        update.callback_query = query
        asyncio.run(bot.guide.callback(update, context))
    assert texts.BASE_STORY_TEXT in context.bot.send_message.call_args.kwargs["text"]

    asyncio.run(bot.new_story(chat_update(replies=replies), context))
    prose = buttons(replies[-1][1]["reply_markup"])
    assert prose == ["format:narrative", "format:simulated"]
    reader = repository.find_participant("7")
    assert repository.contribution(reader["id"]) == {"enrolled": False, "pending": True}

    repository.bind_contribution("7", "job")
    assert repository.complete_generation("7", "job", synthetic_run(tmp_path / "base", 1))
    asyncio.run(bot._after_delivery(context, 7, SimpleNamespace(id=7), True))
    assert texts.READY_COLLECTION in context.bot.send_message.call_args.kwargs["text"]

    asyncio.run(bot.new_story(chat_update(replies=replies), context))
    formats = [
        b.callback_data for row in replies[-1][1]["reply_markup"].inline_keyboard for b in row
    ]
    assert "format:script-native" in formats
    assert context.user_data["contributing"] is False


def test_the_gate_swallows_everything_until_the_key_is_given(tmp_path):
    bot = experiment(tmp_path)
    gate = AccessGate(bot.queue, "clave-del-estudio", bot.guide)
    context = chat_context()

    replies: list = []
    with pytest.raises(ApplicationHandlerStop):
        asyncio.run(gate.guard(chat_update(text="/newstory", replies=replies), context))
    assert replies[-1][0] == texts.LOCKED_TEXT

    callback = chat_update()
    callback.callback_query = SimpleNamespace(answer=AsyncMock())
    with pytest.raises(ApplicationHandlerStop):
        asyncio.run(gate.guard(callback, context))
    callback.callback_query.answer.assert_awaited_with(texts.CALLBACK_LOCKED, show_alert=True)

    with pytest.raises(ApplicationHandlerStop):
        asyncio.run(gate.guard(chat_update(text="otra", replies=replies), context))
    assert replies[-1][0] == texts.KEY_REJECTED.format(remaining=MAX_FAILURES - 1)

    accepted = chat_update(text="  clave-del-estudio ", replies=replies)
    with pytest.raises(ApplicationHandlerStop):
        asyncio.run(gate.guard(accepted, context))
    accepted.effective_message.delete.assert_awaited()
    assert texts.CONSENT_TEXT in context.bot.send_message.call_args.kwargs["text"]
    assert asyncio.run(gate.guard(chat_update(text="/start"), context)) is None


def test_phase_announcements_reach_each_participant_once(tmp_path):
    repository = prepare_demo(tmp_path / "study", readers=3)
    bot = experiment(tmp_path, repository)
    with repository.transaction() as db:
        db.execute(
            "UPDATE participants SET external_id=substr(external_id, 18) + 100 "
            "WHERE external_id LIKE 'synthetic-reader-%'"
        )
    for user_id in (100, 101):
        bot.queue.grant(user_id)
        bot.queue.set_consent(user_id, True)
    send = AsyncMock()
    announcer = PhaseAnnouncer(bot.guide)
    assert asyncio.run(announcer.announce(SimpleNamespace(send_message=send))) == 2
    first = send.call_args.kwargs
    assert first["text"].startswith(texts.ANNOUNCEMENT_HEADERS["evaluation"])
    assert first["reply_markup"].inline_keyboard[0][0].callback_data == "guide:evaluate"
    assert asyncio.run(announcer.announce(SimpleNamespace(send_message=send))) == 0
