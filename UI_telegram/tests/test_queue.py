from pathlib import Path

from asg_telegram.queue import QueueRepository


def test_queue_is_fifo_and_blocks_duplicate_active_user(tmp_path: Path) -> None:
    queue = QueueRepository(tmp_path / "queue.sqlite3")
    first = queue.enqueue(user_id=1, username="uno", chat_id=10, prompt="a")
    second = queue.enqueue(user_id=2, username="dos", chat_id=20, prompt="b")
    duplicate = queue.enqueue(user_id=1, username="uno", chat_id=10, prompt="otra")
    assert duplicate.id == first.id
    assert queue.position(first.id) == 1
    assert queue.position(second.id) == 2


def test_cancel_removes_queued_user_and_updates_position(tmp_path: Path) -> None:
    queue = QueueRepository(tmp_path / "queue.sqlite3")
    first = queue.enqueue(user_id=1, username="uno", chat_id=10, prompt="a")
    second = queue.enqueue(user_id=2, username="dos", chat_id=20, prompt="b")
    queue.mark_running(first.id)
    assert queue.cancel_user(2)
    assert queue.position(second.id) is None
    assert not queue.cancel_user(1)


def test_running_job_is_requeued_at_front_after_restart(tmp_path: Path) -> None:
    path = tmp_path / "queue.sqlite3"
    queue = QueueRepository(path)
    first = queue.enqueue(user_id=1, username="uno", chat_id=10, prompt="a")
    queue.enqueue(user_id=2, username="dos", chat_id=20, prompt="b")
    queue.mark_running(first.id)
    restarted = QueueRepository(path)
    restored = restarted.recover_interrupted()
    assert restored[0].id == first.id
    assert restored[0].status == "queued"
    assert restored[0].recovery_count == 1
    assert restarted.last_recovered_ids == {first.id}


def test_queue_persists_run_directory(tmp_path: Path) -> None:
    queue = QueueRepository(tmp_path / "queue.sqlite3")
    job = queue.enqueue(user_id=1, username="uno", chat_id=10, prompt="a")
    queue.set_run_dir(job.id, "Stories/run-1")
    assert QueueRepository(queue.path).get(job.id).run_dir == "Stories/run-1"


def test_estimate_requires_ten_completed_stories(tmp_path: Path) -> None:
    queue = QueueRepository(tmp_path / "queue.sqlite3")
    with queue._connect() as db:
        for index in range(9):
            db.execute(
                "INSERT INTO jobs(id,user_id,username,chat_id,prompt,status,enqueued_at,"
                "finished_at,duration_seconds) VALUES(?,?,?,?,?,'completed',?,?,?)",
                (str(index), index, "user", index, "prompt", f"2026-01-{index + 1:02d}",
                 f"2026-01-{index + 1:02d}", 60.0),
            )
    assert queue.average_duration() is None
