import sqlite3
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
