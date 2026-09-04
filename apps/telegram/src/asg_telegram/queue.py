"""Provide the durable SQLite queue used by the Telegram application."""

from __future__ import annotations

import sqlite3
import threading
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class QueueJob:
    """Represent one persisted Telegram story-generation job."""

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
    """Store and update Telegram jobs in a thread-safe FIFO queue."""

    def __init__(self, path: Path) -> None:
        """Open a queue database and create its schema when necessary."""
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self._lock = threading.RLock()
        self.last_recovered_ids: set[str] = set()
        with self._connect() as db:
            db.execute(
                """CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY, user_id INTEGER NOT NULL,
                    username TEXT NOT NULL, chat_id INTEGER NOT NULL,
                    prompt TEXT NOT NULL, status TEXT NOT NULL,
                    enqueued_at TEXT NOT NULL, started_at TEXT, finished_at TEXT,
                    progress_message_id INTEGER, run_dir TEXT,
                    recovery_count INTEGER NOT NULL DEFAULT 0,
                    duration_seconds REAL, error_code TEXT
                )"""
            )

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        """Yield a configured connection, closing it deterministically."""
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    @staticmethod
    def _job(row: sqlite3.Row) -> QueueJob:
        """Convert a database row into the public queue-job model."""
        values: dict[str, Any] = {key: row[key] for key in QueueJob.__dataclass_fields__}
        return QueueJob(**values)

    def enqueue(
        self,
        *,
        user_id: int,
        username: str,
        chat_id: int,
        prompt: str,
        progress_message_id: int | None = None,
    ) -> QueueJob:
        """Append a job unless the user already has an active request."""
        with self._lock, self._connect() as db:
            existing = db.execute(
                "SELECT * FROM jobs WHERE user_id=? AND status IN ('queued','running')",
                (user_id,),
            ).fetchone()
            if existing:
                return self._job(existing)
            job = QueueJob(
                str(uuid.uuid4()),
                user_id,
                username,
                chat_id,
                prompt,
                "queued",
                datetime.now(UTC).isoformat(),
                progress_message_id,
            )
            db.execute(
                "INSERT INTO jobs(id,user_id,username,chat_id,prompt,status,enqueued_at,"
                "progress_message_id) VALUES(?,?,?,?,?,?,?,?)",
                (
                    job.id,
                    job.user_id,
                    job.username,
                    job.chat_id,
                    job.prompt,
                    job.status,
                    job.enqueued_at,
                    progress_message_id,
                ),
            )
            return job

    def active(self) -> list[QueueJob]:
        """Return running and queued jobs in their effective FIFO order."""
        with self._lock, self._connect() as db:
            rows = db.execute(
                "SELECT * FROM jobs WHERE status IN ('running','queued') "
                "ORDER BY CASE status WHEN 'running' THEN 0 ELSE 1 END, enqueued_at"
            ).fetchall()
        return [self._job(row) for row in rows]

    def get(self, job_id: str) -> QueueJob | None:
        """Return a job by identifier, or None when it does not exist."""
        with self._lock, self._connect() as db:
            row = db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        return self._job(row) if row else None

    def position(self, job_id: str) -> int | None:
        """Return the one-based active queue position for a job."""
        return next(
            (index for index, job in enumerate(self.active(), 1) if job.id == job_id),
            None,
        )

    def mark_running(self, job_id: str) -> None:
        """Mark a queued job as running and record its start time."""
        with self._lock, self._connect() as db:
            db.execute(
                "UPDATE jobs SET status='running', started_at=? WHERE id=?",
                (datetime.now(UTC).isoformat(), job_id),
            )

    def set_run_dir(self, job_id: str, run_dir: str) -> None:
        """Associate a generated run directory with a queue job."""
        with self._lock, self._connect() as db:
            db.execute("UPDATE jobs SET run_dir=? WHERE id=?", (run_dir, job_id))

    def set_progress_message(self, job_id: str, message_id: int) -> None:
        """Store the Telegram message used to report job progress."""
        with self._lock, self._connect() as db:
            db.execute(
                "UPDATE jobs SET progress_message_id=? WHERE id=?",
                (message_id, job_id),
            )

    def finish(self, job_id: str, status: str, *, error_code: str | None = None) -> None:
        """Persist a terminal job status and its measured duration."""
        if status not in {"completed", "failed", "cancelled"}:
            raise ValueError("invalid terminal queue status")
        now = datetime.now(UTC).isoformat()
        with self._lock, self._connect() as db:
            db.execute(
                """UPDATE jobs SET status=?, finished_at=?, error_code=?,
                    duration_seconds=(julianday(?) - julianday(started_at))*86400
                    WHERE id=?""",
                (status, now, error_code, now, job_id),
            )

    def cancel_user(self, user_id: int) -> bool:
        """Cancel a user's queued job and report whether one was found."""
        with self._lock, self._connect() as db:
            row = db.execute(
                "SELECT id FROM jobs WHERE user_id=? AND status='queued'", (user_id,)
            ).fetchone()
            if not row:
                return False
            db.execute(
                "UPDATE jobs SET status='cancelled', finished_at=? WHERE id=?",
                (datetime.now(UTC).isoformat(), row["id"]),
            )
            return True

    def recover_interrupted(self) -> list[QueueJob]:
        """Quarantine interrupted jobs and return work that can continue."""
        with self._lock, self._connect() as db:
            self.last_recovered_ids = {
                row[0]
                for row in db.execute("SELECT id FROM jobs WHERE status='running'").fetchall()
            }
            db.execute(
                """UPDATE jobs SET status='recovery_pending',
                    recovery_count=recovery_count+1,
                    error_code='RECOVERY_NOT_IMPLEMENTED'
                    WHERE status='running'"""
            )
        return self.active()

    def recovery_pending(self) -> list[QueueJob]:
        """Return interrupted jobs waiting for an explicit recovery policy."""
        with self._lock, self._connect() as db:
            rows = db.execute(
                "SELECT * FROM jobs WHERE status='recovery_pending' ORDER BY enqueued_at"
            ).fetchall()
        return [self._job(row) for row in rows]

    def average_duration(self) -> float | None:
        """Average the ten most recent completed jobs when available."""
        with self._lock, self._connect() as db:
            rows = db.execute(
                "SELECT duration_seconds FROM jobs WHERE status='completed' "
                "AND duration_seconds IS NOT NULL ORDER BY finished_at DESC LIMIT 10"
            ).fetchall()
        return sum(row[0] for row in rows) / len(rows) if len(rows) == 10 else None
