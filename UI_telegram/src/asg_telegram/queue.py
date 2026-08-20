"""Durable FIFO queue for Telegram story jobs."""

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
import threading
import uuid


@dataclass(slots=True)
class QueueJob:
    id: str
    user_id: int
    username: str
    chat_id: int
    prompt: str
    status: str
    enqueued_at: str
    progress_message_id: int | None = None
    run_dir: str | None = None
    recovery_count: int = 0
    error_code: str | None = None


class QueueRepository:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self._lock = threading.RLock()
        self.last_recovered_ids: set[str] = set()
        with self._connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY, user_id INTEGER NOT NULL, username TEXT NOT NULL,
                chat_id INTEGER NOT NULL, prompt TEXT NOT NULL, status TEXT NOT NULL,
                enqueued_at TEXT NOT NULL, started_at TEXT, finished_at TEXT,
                progress_message_id INTEGER, run_dir TEXT, recovery_count INTEGER NOT NULL DEFAULT 0,
                duration_seconds REAL, error_code TEXT
            )""")

    def _connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        return db

    @staticmethod
    def _job(row) -> QueueJob:
        return QueueJob(**{key: row[key] for key in QueueJob.__dataclass_fields__})

    def enqueue(self, *, user_id: int, username: str, chat_id: int, prompt: str,
                progress_message_id: int | None = None) -> QueueJob:
        with self._lock, self._connect() as db:
            existing = db.execute(
                "SELECT * FROM jobs WHERE user_id=? AND status IN ('queued','running')", (user_id,)
            ).fetchone()
            if existing:
                return self._job(existing)
            job = QueueJob(str(uuid.uuid4()), user_id, username, chat_id, prompt, "queued",
                           datetime.now(timezone.utc).isoformat(), progress_message_id)
            db.execute("INSERT INTO jobs(id,user_id,username,chat_id,prompt,status,enqueued_at,progress_message_id) VALUES(?,?,?,?,?,?,?,?)",
                       (job.id, job.user_id, job.username, job.chat_id, job.prompt, job.status, job.enqueued_at, progress_message_id))
            return job

    def active(self) -> list[QueueJob]:
        with self._connect() as db:
            rows = db.execute("SELECT * FROM jobs WHERE status IN ('running','queued') ORDER BY CASE status WHEN 'running' THEN 0 ELSE 1 END, enqueued_at").fetchall()
        return [self._job(row) for row in rows]

    def get(self, job_id: str) -> QueueJob | None:
        with self._connect() as db:
            row = db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        return self._job(row) if row else None

    def position(self, job_id: str) -> int | None:
        return next((i for i, job in enumerate(self.active(), 1) if job.id == job_id), None)

    def mark_running(self, job_id: str) -> None:
        with self._lock, self._connect() as db:
            db.execute("UPDATE jobs SET status='running', started_at=? WHERE id=?", (datetime.now(timezone.utc).isoformat(), job_id))

    def set_run_dir(self, job_id: str, run_dir: str) -> None:
        with self._lock, self._connect() as db:
            db.execute("UPDATE jobs SET run_dir=? WHERE id=?", (run_dir, job_id))

    def set_progress_message(self, job_id: str, message_id: int) -> None:
        with self._lock, self._connect() as db:
            db.execute("UPDATE jobs SET progress_message_id=? WHERE id=?", (message_id, job_id))

    def finish(self, job_id: str, status: str, *, error_code: str | None = None) -> None:
        if status not in {"completed", "failed", "cancelled"}:
            raise ValueError("invalid terminal queue status")
        with self._lock, self._connect() as db:
            db.execute("""UPDATE jobs SET status=?, finished_at=?, error_code=?,
                duration_seconds=(julianday(?) - julianday(started_at))*86400 WHERE id=?""",
                (status, datetime.now(timezone.utc).isoformat(), error_code,
                 datetime.now(timezone.utc).isoformat(), job_id))

    def cancel_user(self, user_id: int) -> bool:
        with self._lock, self._connect() as db:
            row = db.execute("SELECT id FROM jobs WHERE user_id=? AND status='queued'", (user_id,)).fetchone()
            if not row:
                return False
            db.execute("UPDATE jobs SET status='cancelled', finished_at=? WHERE id=?",
                       (datetime.now(timezone.utc).isoformat(), row["id"]))
            return True

    def recover_interrupted(self) -> list[QueueJob]:
        with self._lock, self._connect() as db:
            self.last_recovered_ids = {
                row[0] for row in db.execute(
                    "SELECT id FROM jobs WHERE status='running'"
                ).fetchall()
            }
            # TODO(recovery-4.x): rebuild STORYLINE/NEKG from the final checkpoint,
            # continue the first pending provider call, and deliver to the original user.
            db.execute("""UPDATE jobs SET status='recovery_pending',
                recovery_count=recovery_count+1, error_code='RECOVERY_NOT_IMPLEMENTED'
                WHERE status='running'""")
        return self.active()

    def recovery_pending(self) -> list[QueueJob]:
        with self._connect() as db:
            rows = db.execute(
                "SELECT * FROM jobs WHERE status='recovery_pending' ORDER BY enqueued_at"
            ).fetchall()
        return [self._job(row) for row in rows]

    def average_duration(self) -> float | None:
        with self._connect() as db:
            rows = db.execute("SELECT duration_seconds FROM jobs WHERE status='completed' AND duration_seconds IS NOT NULL ORDER BY finished_at DESC LIMIT 10").fetchall()
        # A full ten-job window avoids presenting a misleading estimate from a
        # single unusually short or long story.
        return sum(row[0] for row in rows) / len(rows) if len(rows) == 10 else None
