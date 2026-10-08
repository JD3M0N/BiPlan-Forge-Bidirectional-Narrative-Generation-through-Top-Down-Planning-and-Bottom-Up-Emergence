import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from asg_telegram.queue import QueueRepository


def test_queue_is_fifo_blocks_duplicates_and_withholds_early_estimates(tmp_path: Path) -> None:
    """FIFO order, one active job per user, and no duration estimate below the sample floor."""
    queue = QueueRepository(tmp_path / "queue.sqlite3")
    first = queue.enqueue(user_id=1, username="uno", chat_id=10, prompt="a").job
    second = queue.enqueue(user_id=2, username="dos", chat_id=20, prompt="b").job
    duplicate = queue.enqueue(user_id=1, username="uno", chat_id=10, prompt="otra")
    assert duplicate.job.id == first.id
    assert not duplicate.created
    assert queue.position(first.id) == 1
    assert queue.position(second.id) == 2

    with queue._connect() as db:
        for index in range(2):
            db.execute(
                "INSERT INTO jobs(id,user_id,username,chat_id,prompt,status,enqueued_at,"
                "finished_at,duration_seconds) VALUES(?,?,?,?,?,'completed',?,?,?)",
                (
                    f"done-{index}",
                    100 + index,
                    "user",
                    index,
                    "prompt",
                    f"2026-01-{index + 1:02d}",
                    f"2026-01-{index + 1:02d}",
                    60.0,
                ),
            )
    assert queue.average_duration() is None


def test_cancel_removes_queued_user_and_updates_position(tmp_path: Path) -> None:
    queue = QueueRepository(tmp_path / "queue.sqlite3")
    first = queue.enqueue(user_id=1, username="uno", chat_id=10, prompt="a").job
    second = queue.enqueue(user_id=2, username="dos", chat_id=20, prompt="b").job
    queue.mark_running(first.id)
    assert queue.cancel_user(2) == "cancelled"
    assert queue.position(second.id) is None
    assert queue.cancel_user(1) == "requested"
    assert queue.cancellation_requested(first.id)
    assert queue.cancel_user(99) is None


def test_running_job_becomes_recovery_pending_and_queue_continues(tmp_path: Path) -> None:
    path = tmp_path / "queue.sqlite3"
    queue = QueueRepository(path)
    first = queue.enqueue(user_id=1, username="uno", chat_id=10, prompt="a").job
    queue.enqueue(user_id=2, username="dos", chat_id=20, prompt="b")
    queue.mark_running(first.id)
    queue.set_run_dir(first.id, "Stories/run-1")

    restarted = QueueRepository(path)
    restored = restarted.recover_interrupted()
    assert len(restored) == 1
    assert restored[0].user_id == 2
    pending = restarted.recovery_pending()
    assert pending[0].id == first.id
    assert pending[0].status == "recovery_pending"
    assert pending[0].recovery_count == 1
    assert pending[0].run_dir == "Stories/run-1"
    assert restarted.get(first.id).error_code == "RECOVERY_NOT_IMPLEMENTED"
    assert restarted.last_recovered_ids == {first.id}


def test_user_preferences_survive_reopening_the_database(tmp_path: Path) -> None:
    path = tmp_path / "queue.sqlite3"
    queue = QueueRepository(path)
    queue.save_user_options(1, {"promise_ledger": False, "turns_per_beat": 6})
    assert queue.user_options(1) == {"promise_ledger": False, "turns_per_beat": 6}

    reopened = QueueRepository(path)
    assert reopened.user_options(1) == {"promise_ledger": False, "turns_per_beat": 6}
    assert reopened.user_options(2) == {}

    reopened.clear_user_options(1)
    assert reopened.user_options(1) == {}


def test_options_and_brief_round_trip_through_a_job(tmp_path: Path) -> None:
    queue = QueueRepository(tmp_path / "queue.sqlite3")
    job = queue.enqueue(
        user_id=1,
        username="uno",
        chat_id=10,
        prompt="Una archivera y un secreto",
        options={"format": "simulated", "turns_per_beat": 6},
        brief={"plot": "Una trama", "cast": [{"name": "Ana"}]},
    ).job
    reopened = queue.get(job.id)
    assert reopened.options == {"format": "simulated", "turns_per_beat": 6}
    assert reopened.brief == {"plot": "Una trama", "cast": [{"name": "Ana"}]}


def test_unreadable_job_json_is_treated_as_absent(tmp_path: Path) -> None:
    queue = QueueRepository(tmp_path / "queue.sqlite3")
    job = queue.enqueue(user_id=1, username="uno", chat_id=10, prompt="a").job
    with queue._connect() as db:
        db.execute("UPDATE jobs SET options=? WHERE id=?", ("{not json", job.id))
    assert queue.get(job.id).options is None


def test_a_v3_database_migrates_to_the_current_schema_and_keeps_its_jobs(tmp_path: Path) -> None:
    path = tmp_path / "queue.sqlite3"
    with sqlite3.connect(path) as db:
        db.execute(
            """CREATE TABLE jobs (
                id TEXT PRIMARY KEY, user_id INTEGER NOT NULL,
                username TEXT NOT NULL, chat_id INTEGER NOT NULL,
                prompt TEXT NOT NULL, status TEXT NOT NULL,
                enqueued_at TEXT NOT NULL, started_at TEXT, finished_at TEXT,
                progress_message_id INTEGER, run_dir TEXT,
                recovery_count INTEGER NOT NULL DEFAULT 0,
                duration_seconds REAL, error_code TEXT,
                narrative_profile TEXT,
                cancel_requested INTEGER NOT NULL DEFAULT 0,
                story_format TEXT
            )"""
        )
        db.execute(
            "INSERT INTO jobs(id,user_id,username,chat_id,prompt,status,enqueued_at,"
            "narrative_profile,story_format) VALUES('v3-job',1,'ana',10,'Un cuento','queued',"
            "'2026-01-01','developed','narrative')"
        )
        db.execute("PRAGMA user_version = 3")

    queue = QueueRepository(path)
    job = queue.get("v3-job")
    assert job.narrative_profile == "developed"
    assert job.story_format == "narrative"
    assert job.options is None
    queue.save_user_options(1, {"promise_ledger": False})
    assert queue.user_options(1) == {"promise_ledger": False}
    queue.grant(1)
    assert queue.access(1)["granted_at"]


def test_access_locks_after_the_limit_and_remembers_consent_and_announcements(
    tmp_path: Path,
) -> None:
    """Wrong keys count down to a lockout; a later grant clears it; both answers persist."""
    queue = QueueRepository(tmp_path / "queue.sqlite3")
    lock = timedelta(minutes=15)
    assert [queue.record_failure(5, limit=3, lock=lock) for _ in range(3)] == [2, 1, 0]
    assert queue.locked_until(5) > datetime.now(UTC)
    assert queue.access(5) is None
    queue.grant(5)
    assert queue.locked_until(5) is None
    assert queue.consented_ids() == []
    queue.set_consent(5, False)
    assert queue.access(5)["declined_at"] and not queue.access(5)["consented_at"]
    queue.set_consent(5, True)
    reopened = QueueRepository(tmp_path / "queue.sqlite3")
    assert reopened.consented_ids() == [5]
    assert not reopened.announced(5, "evaluation")
    reopened.mark_announced(5, "evaluation")
    reopened.mark_announced(5, "evaluation")
    assert reopened.announced(5, "evaluation")


def test_every_operation_closes_its_connection(tmp_path: Path, monkeypatch) -> None:
    opened: list[sqlite3.Connection] = []
    original_connect = sqlite3.connect

    def tracking_connect(*args, **kwargs):
        connection = original_connect(*args, **kwargs)
        opened.append(connection)
        return connection

    monkeypatch.setattr(sqlite3, "connect", tracking_connect)

    queue = QueueRepository(tmp_path / "queue.sqlite3")
    job = queue.enqueue(user_id=1, username="uno", chat_id=10, prompt="a").job
    queue.active()
    queue.get(job.id)
    queue.mark_running(job.id)
    queue.finish(job.id, "completed")
    queue.cancel_user(2)
    queue.recovery_pending()
    queue.average_duration()

    assert opened
    for connection in opened:
        with pytest.raises(sqlite3.ProgrammingError):
            connection.execute("SELECT 1")
