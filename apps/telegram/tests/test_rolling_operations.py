"""Quota-aware scheduling and private research operations without external services."""

import asyncio
import base64
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from asg_evaluation.demo import synthetic_run
from asg_evaluation.study import StudyRepository
from asg_telegram.contract import GenerationAvailability, GenerationFailure
from asg_telegram.generation import GenerationCoordinator
from asg_telegram.public_pool import GitHubPool, PoolPublisher
from asg_telegram.queue import QueueRepository
from asg_telegram.research_admin import ResearchAdmin
from telegram_fakes import FakeGenerator


def enqueue(queue, number, priority=2):
    return queue.enqueue(
        user_id=number,
        username="reader",
        chat_id=number,
        prompt=f"idea-{number}",
        priority=priority,
    ).job


def test_priority_fifo_cooldown_cancel_and_restart(tmp_path):
    queue = QueueRepository(tmp_path / "queue.sqlite3")
    free = enqueue(queue, 1)
    replacement = enqueue(queue, 2, 1)
    first = enqueue(queue, 3, 0)
    other = enqueue(queue, 4, 0)
    assert [job.id for job in queue.active()] == [first.id, other.id, replacement.id, free.id]
    tomorrow = (datetime.now(UTC) + timedelta(days=1)).isoformat()
    queue.defer(first.id, tomorrow, "daily quota")
    restored = QueueRepository(queue.path)
    restored.recover_interrupted()
    assert restored.get(first.id).prompt == "idea-3"
    assert restored.get(first.id).recovery_count == 0
    assert restored.next_ready() == other.id
    assert not restored.enqueue(user_id=3, username="", chat_id=3, prompt="duplicate").created
    assert restored.cancel_user(3) == "cancelled"
    assert restored.get(first.id).status == "cancelled"


def test_scheduler_honors_priority_even_if_free_task_starts_first(tmp_path):
    queue = QueueRepository(tmp_path / "queue.sqlite3")
    free = enqueue(queue, 1)
    first = enqueue(queue, 2, 0)
    coordinator = GenerationCoordinator(FakeGenerator(tmp_path), queue)
    telegram = SimpleNamespace(edit_message_text=AsyncMock(), send_message=AsyncMock())
    context = SimpleNamespace(bot=telegram, application=SimpleNamespace(bot=telegram))
    order = []

    async def run_generation(**kwargs):
        order.append(kwargs["job_id"])
        queue.finish(kwargs["job_id"], "completed")

    coordinator._run_generation_and_delivery = run_generation

    async def exercise():
        await asyncio.wait_for(
            asyncio.gather(
                *[
                    coordinator._generate_and_deliver(
                        context=context,
                        chat_id=job.chat_id,
                        user=SimpleNamespace(id=job.user_id),
                        prompt=job.prompt,
                        job_id=job.id,
                    )
                    for job in (free, first)
                ]
            ),
            timeout=5,
        )

    asyncio.run(exercise())
    assert order == [first.id, free.id]


def test_daily_quota_keeps_bound_contribution_and_retries_without_user_input(tmp_path):
    queue = QueueRepository(tmp_path / "queue.sqlite3")
    job = enqueue(queue, 1, 0)
    coordinator = GenerationCoordinator(FakeGenerator(tmp_path), queue)
    coordinator.generator.availability = lambda options: GenerationAvailability(
        False, (datetime.now(UTC) - timedelta(seconds=1)).isoformat(), "daily quota"
    )
    telegram = SimpleNamespace(edit_message_text=AsyncMock(), send_message=AsyncMock())
    context = SimpleNamespace(bot=telegram, application=SimpleNamespace(bot=telegram), user_data={})
    release = Mock()
    coordinator.study = SimpleNamespace(
        repository=SimpleNamespace(release_contribution=release, assigned_format=lambda *_: None)
    )
    user = SimpleNamespace(id=1, username="reader", full_name="Reader")
    error = GenerationFailure(
        "quota", code="GEMINI_DAILY_QUOTA_EXHAUSTED", stage="plan", retryable_quota=True
    )
    asyncio.run(coordinator._handle_generation_failure(error, context, 1, user, job.id, None, []))
    assert queue.get(job.id).status == "quota_wait"
    release.assert_not_called()
    coordinator.generator.availability = lambda options: GenerationAvailability()

    async def complete(**kwargs):
        queue.finish(kwargs["job_id"], "completed")

    coordinator._run_generation_and_delivery = complete
    asyncio.run(
        coordinator._generate_and_deliver(
            context=context, chat_id=1, user=user, prompt=job.prompt, job_id=job.id
        )
    )
    assert queue.get(job.id).status == "completed"


def test_preflight_blocks_without_consuming_generation_and_can_be_cancelled(tmp_path):
    queue = QueueRepository(tmp_path / "queue.sqlite3")
    job = enqueue(queue, 1)
    generator = FakeGenerator(tmp_path)
    generator.availability = lambda options: GenerationAvailability(
        False, (datetime.now(UTC) + timedelta(days=1)).isoformat(), "daily quota"
    )
    coordinator = GenerationCoordinator(generator, queue)
    application = SimpleNamespace(bot=SimpleNamespace(edit_message_text=AsyncMock()))

    async def exercise():
        task = asyncio.create_task(coordinator._wait_for_turn(job.id, {}, application))
        for _ in range(100):
            if queue.get(job.id).status == "quota_wait":
                break
            await asyncio.sleep(0.01)
        assert queue.get(job.id).status == "quota_wait"
        queue.cancel_user(1)
        assert await asyncio.wait_for(task, timeout=3) is False

    asyncio.run(exercise())


def public_repository(tmp_path):
    repository = StudyRepository(tmp_path / "study.sqlite3")
    repository.create("rolling", required_version="DEMO-1", mode="rolling")
    repository.transition("collection")
    sid = repository.add_story(synthetic_run(tmp_path / "seed", 0), curated=True)
    story = repository.publication_candidates()[0]
    repository.approve_publication(sid, story["text_hash"])
    return repository, story


def test_github_outage_persists_backoff_and_success_is_idempotent(tmp_path):
    repository, story = public_repository(tmp_path)
    remote = Mock()
    remote.publish.side_effect = OSError("offline")
    publisher = PoolPublisher(repository, remote)
    assert publisher.sync() == 0
    assert repository.publication_batch()[0]["attempts"] == 1
    assert publisher.sync() == 0
    assert remote.publish.call_count == 1
    with repository.transaction() as db:
        db.execute("UPDATE publications SET next_attempt=NULL")
    remote.publish.side_effect = None
    assert publisher.sync() == 1
    assert publisher.sync() == 0
    assert repository.publication_batch()[0]["synced_at"]
    assert repository.info()["state"] == "collection"


def test_github_manifest_has_only_public_fields_and_nonforced_atomic_commit():
    pool = GitHubPool("owner/repo", "private-token")
    requests = []

    def request(path, data=None, **kwargs):
        requests.append((path, data, kwargs))
        if path.startswith("/git/ref/"):
            return {"object": {"sha": "head"}}
        if path == "/git/commits/head":
            return {"tree": {"sha": "tree"}}
        if path.startswith("/contents/"):
            return {
                "content": base64.b64encode(
                    json.dumps({"schema_version": 1, "stories": []}).encode()
                ).decode()
            }
        return {"sha": "new"}

    pool.request = request
    pool.publish(
        [
            {
                "id": "s123",
                "text": "public text",
                "text_hash": "hash",
                "provenance": {"private": "must not publish"},
            }
        ]
    )
    entries = next(data["tree"] for path, data, _ in requests if path == "/git/trees")
    assert "must not publish" not in json.dumps(entries)
    assert "private-token" not in json.dumps(entries)
    manifest = json.loads(entries[-1]["content"])
    assert manifest["stories"] == [{"id": "s123", "text_hash": "hash"}]
    assert requests[-1][1]["force"] is False
    assert requests[-1][2]["method"] == "PATCH"


@pytest.mark.parametrize(("user", "chat_type"), [(9, "private"), (1, "group")])
def test_admin_export_and_approval_reject_wrong_identity_or_group(tmp_path, user, chat_type):
    repository, story = public_repository(tmp_path)
    admin = ResearchAdmin(repository, frozenset({1}))
    update = SimpleNamespace(
        effective_user=SimpleNamespace(id=user),
        effective_chat=SimpleNamespace(id=user, type=chat_type),
        effective_message=SimpleNamespace(reply_text=AsyncMock()),
    )
    context = SimpleNamespace(
        bot=SimpleNamespace(send_document=AsyncMock()), args=[story["id"], story["text_hash"]]
    )
    asyncio.run(admin.export(update, context))
    asyncio.run(admin.approve(update, context))
    context.bot.send_document.assert_not_called()


def test_admin_export_sends_zip_in_private_chat(tmp_path):
    repository, _ = public_repository(tmp_path)
    admin = ResearchAdmin(repository, frozenset({1}))
    update = SimpleNamespace(
        effective_user=SimpleNamespace(id=1),
        effective_chat=SimpleNamespace(id=1, type="private"),
        effective_message=SimpleNamespace(reply_text=AsyncMock()),
    )
    context = SimpleNamespace(bot=SimpleNamespace(send_document=AsyncMock()))
    asyncio.run(admin.export(update, context))
    document = context.bot.send_document.call_args.kwargs
    assert document["filename"] == "estudio.zip"
    assert document["document"].getvalue().startswith(b"PK")


def test_background_shutdown_leaves_waiting_job_for_restart(tmp_path):
    queue = QueueRepository(tmp_path / "queue.sqlite3")
    job = enqueue(queue, 1)
    queue.defer(job.id, (datetime.now(UTC) + timedelta(days=1)).isoformat(), "quota")
    coordinator = GenerationCoordinator(FakeGenerator(tmp_path), queue)
    context = SimpleNamespace(
        application=SimpleNamespace(bot=SimpleNamespace()), bot=SimpleNamespace(), user_data={}
    )

    async def exercise():
        task = coordinator.background_task(
            context.application,
            coordinator._generate_and_deliver(
                context=context,
                chat_id=1,
                user=SimpleNamespace(id=1),
                prompt=job.prompt,
                job_id=job.id,
            ),
        )
        await asyncio.sleep(0.01)
        await asyncio.wait_for(coordinator.stop_generation_tasks(), timeout=2)
        assert task.cancelled()

    asyncio.run(exercise())
    assert QueueRepository(queue.path).get(job.id).status == "quota_wait"


def test_cancelling_waiting_contribution_allows_next_job_to_bind(tmp_path):
    from asg_telegram.handlers import TelegramStoryBot
    from asg_telegram.study import StudyConversation

    repository = StudyRepository(tmp_path / "study.sqlite3")
    repository.create("rolling", required_version="DEMO-1", mode="rolling")
    repository.transition("collection")
    reader = repository.participant("1", profile="regular")["id"]
    repository.request_contribution(reader)
    queue = QueueRepository(tmp_path / "queue.sqlite3")
    first = enqueue(queue, 1)
    repository.bind_contribution("1", first.id)
    bot = TelegramStoryBot(FakeGenerator(tmp_path), queue)
    bot.study = StudyConversation(repository, bot)
    update = SimpleNamespace(
        effective_user=SimpleNamespace(id=1, username="a", full_name="a"),
        effective_message=SimpleNamespace(reply_text=AsyncMock()),
    )
    telegram = SimpleNamespace(edit_message_text=AsyncMock())
    context = SimpleNamespace(application=SimpleNamespace(bot=telegram), user_data={})
    asyncio.run(bot.cancel(update, context))
    second = enqueue(queue, 1)
    repository.bind_contribution("1", second.id)
    assert repository.complete_generation("1", second.id, synthetic_run(tmp_path / "run", 7))


def test_stagecraft_capacity_tracks_main_and_stage_separately(tmp_path):
    from asg_stagecraft.runtime.budget import QuotaLedger, QuotaSlot
    from asg_telegram.generators import StagecraftGenerator

    primary = QuotaSlot("gemini", "primary", "utc_day")
    stage = QuotaSlot("gemini", "stage", "utc_day")
    generator = StagecraftGenerator.__new__(StagecraftGenerator)
    generator._settings = SimpleNamespace(
        budget_path=tmp_path / "quota.sqlite3",
        model="primary",
        effective_stage_model="stage",
        chain=(),
        quota_entries=lambda: [SimpleNamespace(slot=primary), SimpleNamespace(slot=stage)],
    )
    ledger = QuotaLedger(generator._settings.budget_path)
    until = ledger.mark_exhausted(stage)
    assert generator.availability({"format": "narrative"}).available
    capacity = generator.availability({"format": "simulated"})
    assert not capacity.available
    assert capacity.retry_at == until.isoformat()
    generator._settings.chain = ("fallback",)
    assert generator.availability({"format": "simulated"}).available
    ledger.mark_exhausted(primary)
    assert not generator.availability({"format": "simulated"}).available


def test_pack_queues_author_stories_once_and_hides_the_participant_format(tmp_path):
    from asg_telegram.guide import ParticipantGuide
    from asg_telegram.handlers import TelegramStoryBot
    from asg_telegram.study import StudyConversation

    repository = StudyRepository(tmp_path / "study.sqlite3")
    repository.create("pack", required_version="DEMO-1", mode="pack")
    prompts = Path(__file__).parents[1] / "pack_author_prompts.json"
    repository.load_author_requests(prompts)
    repository.transition("collection")
    queue = QueueRepository(tmp_path / "queue.sqlite3")
    application = SimpleNamespace(bot=SimpleNamespace(), user_data={i: {} for i in range(-4, 0)})
    for _ in range(2):
        bot = TelegramStoryBot(FakeGenerator(tmp_path), queue)
        bot.study = StudyConversation(repository, bot)
        bot.guide = ParticipantGuide(bot)
        bot.author_chat_id = 99
        bot.schedule = lambda application, coroutine, **kwargs: coroutine.close()
        asyncio.run(bot.ensure_author_jobs(application))
    jobs = queue.active()
    assert sorted(job.user_id for job in jobs) == [-4, -3, -2, -1]
    assert {job.priority for job in jobs} == {1} and {job.chat_id for job in jobs} == {99}
    assert [job.options["format"] for job in sorted(jobs, key=lambda j: -j.user_id)] == [
        entry["format"] for entry in json.loads(prompts.read_text(encoding="utf-8"))
    ]
    queue.grant(7)
    queue.set_consent(7, True)
    repository.participant("7", profile="regular")
    update = SimpleNamespace(
        effective_user=SimpleNamespace(id=7, username="a", full_name="a"),
        effective_message=SimpleNamespace(reply_text=AsyncMock()),
    )
    context = SimpleNamespace(user_data={})
    asyncio.run(bot.new_story(update, context))
    markup = update.effective_message.reply_text.call_args.kwargs["reply_markup"]
    buttons = [button.callback_data for row in markup.inline_keyboard for button in row]
    assert buttons == ["mode:free", "mode:guided"]
    assert bot._generation_priority(7) == 0
    participant = repository.find_participant("7")["id"]
    repository.assign_format(participant)
    repository.bind_contribution("7", "job-7")
    assert bot._blind(7, "job-7") and not bot._blind(-1, jobs[0].id)
