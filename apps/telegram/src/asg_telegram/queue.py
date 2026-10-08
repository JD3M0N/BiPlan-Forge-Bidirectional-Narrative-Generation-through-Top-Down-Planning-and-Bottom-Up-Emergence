"""Provide the durable SQLite queue used by the Telegram application."""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 5
TERMINAL_STATUSES = frozenset({"completed", "failed", "cancelled"})
CANCELLABLE_STATUSES = ("queued", "recovery_pending")
MINIMUM_SAMPLES_FOR_ESTIMATE = 3
DURATION_SAMPLE_SIZE = 10

_SCHEMA = """CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY, user_id INTEGER NOT NULL,
    username TEXT NOT NULL, chat_id INTEGER NOT NULL,
    prompt TEXT NOT NULL, status TEXT NOT NULL,
    enqueued_at TEXT NOT NULL, started_at TEXT, finished_at TEXT,
    progress_message_id INTEGER, run_dir TEXT,
    recovery_count INTEGER NOT NULL DEFAULT 0,
    duration_seconds REAL, error_code TEXT,
    narrative_profile TEXT,
    cancel_requested INTEGER NOT NULL DEFAULT 0,
    story_format TEXT,
    options TEXT,
    brief TEXT
)"""

_USER_OPTIONS_SCHEMA = """CREATE TABLE IF NOT EXISTS user_options (
    user_id INTEGER PRIMARY KEY,
    options TEXT NOT NULL,
    updated_at TEXT NOT NULL
)"""

_ACCESS_SCHEMA = (
    """CREATE TABLE IF NOT EXISTS access (
    user_id INTEGER PRIMARY KEY,
    granted_at TEXT NOT NULL,
    consented_at TEXT,
    declined_at TEXT
)""",
    """CREATE TABLE IF NOT EXISTS access_attempts (
    user_id INTEGER PRIMARY KEY,
    failures INTEGER NOT NULL DEFAULT 0,
    locked_until TEXT
)""",
    """CREATE TABLE IF NOT EXISTS announcements (
    user_id INTEGER NOT NULL,
    phase TEXT NOT NULL,
    sent_at TEXT NOT NULL,
    PRIMARY KEY (user_id, phase)
)""",
)

# Columns introduced after the first unversioned schema, added by migration.
_ADDED_COLUMNS = (
    ("narrative_profile", "narrative_profile TEXT"),
    ("cancel_requested", "cancel_requested INTEGER NOT NULL DEFAULT 0"),
    ("story_format", "story_format TEXT"),
    ("options", "options TEXT"),
    ("brief", "brief TEXT"),
)


def _parse_json(value: str | None) -> dict | None:
    """Parse an optional JSON column, treating unreadable text as absent."""
    if not value:
        return None
    try:
        parsed = json.loads(value)
    except ValueError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _dump_json(value: Mapping | None) -> str | None:
    """Serialize an optional mapping deterministically, or store nothing."""
    if value is None:
        return None
    return json.dumps(dict(value), ensure_ascii=False, sort_keys=True)


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
    narrative_profile: str | None = None
    cancel_requested: int = 0
    story_format: str | None = None
    options: dict | None = None
    brief: dict | None = None


@dataclass(frozen=True, slots=True)
class EnqueueResult:
    """Report whether a request joined the queue or matched an active one."""

    job: QueueJob
    created: bool


class QueueRepository:
    """Store and update Telegram jobs in a thread-safe FIFO queue."""

    def __init__(self, path: Path) -> None:
        """Open a queue database, creating or migrating its schema."""
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self._lock = threading.RLock()
        self.last_recovered_ids: set[str] = set()
        with self._connect() as db:
            self._migrate(db)

    @staticmethod
    def _migrate(db: sqlite3.Connection) -> None:
        """Bring any earlier database up to the current schema in place.

        A database written before ``user_version`` existed reports zero, so the
        added columns are applied one by one and every active job survives.
        """
        if db.execute("PRAGMA user_version").fetchone()[0] >= SCHEMA_VERSION:
            return
        db.execute(_SCHEMA)
        db.execute(_USER_OPTIONS_SCHEMA)
        for statement in _ACCESS_SCHEMA:
            db.execute(statement)
        present = {row["name"] for row in db.execute("PRAGMA table_info(jobs)")}
        for column, definition in _ADDED_COLUMNS:
            if column not in present:
                db.execute(f"ALTER TABLE jobs ADD COLUMN {definition}")
        db.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")

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
        values["options"] = _parse_json(values.get("options"))
        values["brief"] = _parse_json(values.get("brief"))
        return QueueJob(**values)

    def enqueue(
        self,
        *,
        user_id: int,
        username: str,
        chat_id: int,
        prompt: str,
        progress_message_id: int | None = None,
        narrative_profile: str | None = None,
        story_format: str | None = None,
        options: Mapping | None = None,
        brief: Mapping | None = None,
    ) -> EnqueueResult:
        """Append a job unless the user already has an active request."""
        with self._lock, self._connect() as db:
            existing = db.execute(
                "SELECT * FROM jobs WHERE user_id=? AND status IN ('queued','running')",
                (user_id,),
            ).fetchone()
            if existing:
                return EnqueueResult(self._job(existing), created=False)
            job = QueueJob(
                str(uuid.uuid4()),
                user_id,
                username,
                chat_id,
                prompt,
                "queued",
                datetime.now(UTC).isoformat(),
                progress_message_id,
                narrative_profile=narrative_profile,
                story_format=story_format,
                options=dict(options) if options is not None else None,
                brief=dict(brief) if brief is not None else None,
            )
            db.execute(
                "INSERT INTO jobs(id,user_id,username,chat_id,prompt,status,enqueued_at,"
                "progress_message_id,narrative_profile,story_format,options,brief) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    job.id,
                    job.user_id,
                    job.username,
                    job.chat_id,
                    job.prompt,
                    job.status,
                    job.enqueued_at,
                    progress_message_id,
                    narrative_profile,
                    story_format,
                    _dump_json(options),
                    _dump_json(brief),
                ),
            )
            return EnqueueResult(job, created=True)

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
        if status not in TERMINAL_STATUSES:
            raise ValueError("invalid terminal queue status")
        now = datetime.now(UTC).isoformat()
        with self._lock, self._connect() as db:
            db.execute(
                """UPDATE jobs SET status=?, finished_at=?, error_code=?,
                    duration_seconds=(julianday(?) - julianday(started_at))*86400
                    WHERE id=?""",
                (status, now, error_code, now, job_id),
            )

    def requeue(self, job_id: str) -> None:
        """Return an interrupted job to the queue for another attempt."""
        with self._lock, self._connect() as db:
            db.execute(
                "UPDATE jobs SET status='queued', started_at=NULL, error_code=NULL, "
                "cancel_requested=0 WHERE id=? AND status='recovery_pending'",
                (job_id,),
            )

    def cancellation_requested(self, job_id: str) -> bool:
        """Report whether a running job has been asked to stop."""
        with self._lock, self._connect() as db:
            row = db.execute("SELECT cancel_requested FROM jobs WHERE id=?", (job_id,)).fetchone()
        return bool(row and row["cancel_requested"])

    def cancel_user(self, user_id: int) -> str | None:
        """Cancel a user's pending job, or ask a running one to stop.

        Returns ``"cancelled"`` when a job left the queue immediately,
        ``"requested"`` when a running job was flagged to stop at its next
        checkpoint, and None when the user had nothing to cancel.
        """
        placeholders = ",".join("?" * len(CANCELLABLE_STATUSES))
        with self._lock, self._connect() as db:
            row = db.execute(
                f"SELECT id FROM jobs WHERE user_id=? AND status IN ({placeholders})",
                (user_id, *CANCELLABLE_STATUSES),
            ).fetchone()
            if row:
                db.execute(
                    "UPDATE jobs SET status='cancelled', finished_at=? WHERE id=?",
                    (datetime.now(UTC).isoformat(), row["id"]),
                )
                return "cancelled"
            running = db.execute(
                "SELECT id FROM jobs WHERE user_id=? AND status='running'", (user_id,)
            ).fetchone()
            if not running:
                return None
            db.execute("UPDATE jobs SET cancel_requested=1 WHERE id=?", (running["id"],))
            return "requested"

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
                    cancel_requested=0,
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
        """Average the most recent completed jobs once enough have finished."""
        with self._lock, self._connect() as db:
            rows = db.execute(
                "SELECT duration_seconds FROM jobs WHERE status='completed' "
                "AND duration_seconds IS NOT NULL ORDER BY finished_at DESC LIMIT ?",
                (DURATION_SAMPLE_SIZE,),
            ).fetchall()
        if len(rows) < MINIMUM_SAMPLES_FOR_ESTIMATE:
            return None
        return sum(row[0] for row in rows) / len(rows)

    def counts(self) -> dict[str, int]:
        """Return how many jobs are queued and running, for the startup banner."""
        with self._lock, self._connect() as db:
            rows = db.execute(
                "SELECT status, COUNT(*) AS total FROM jobs "
                "WHERE status IN ('queued','running') GROUP BY status"
            ).fetchall()
        return {row["status"]: row["total"] for row in rows}

    def user_options(self, user_id: int) -> dict:
        """Return a user's stored option overrides, or an empty mapping."""
        with self._lock, self._connect() as db:
            row = db.execute(
                "SELECT options FROM user_options WHERE user_id=?", (user_id,)
            ).fetchone()
        return _parse_json(row["options"]) or {} if row else {}

    def save_user_options(self, user_id: int, options: Mapping) -> None:
        """Persist a user's option overrides, replacing any earlier ones."""
        with self._lock, self._connect() as db:
            db.execute(
                """INSERT INTO user_options(user_id, options, updated_at) VALUES(?,?,?)
                    ON CONFLICT(user_id) DO UPDATE SET
                        options=excluded.options, updated_at=excluded.updated_at""",
                (user_id, _dump_json(options), datetime.now(UTC).isoformat()),
            )

    def clear_user_options(self, user_id: int) -> None:
        """Forget a user's stored option overrides."""
        with self._lock, self._connect() as db:
            db.execute("DELETE FROM user_options WHERE user_id=?", (user_id,))

    # --- access and announcements -----------------------------------------

    def access(self, user_id: int) -> dict | None:
        """Return a user's access record, or None when they never gave the key."""
        with self._lock, self._connect() as db:
            row = db.execute("SELECT * FROM access WHERE user_id=?", (user_id,)).fetchone()
        return dict(row) if row else None

    def grant(self, user_id: int) -> None:
        """Authorize a user permanently and forget their failed attempts."""
        with self._lock, self._connect() as db:
            db.execute(
                "INSERT OR IGNORE INTO access(user_id, granted_at) VALUES(?,?)",
                (user_id, datetime.now(UTC).isoformat()),
            )
            db.execute("DELETE FROM access_attempts WHERE user_id=?", (user_id,))

    def locked_until(self, user_id: int) -> datetime | None:
        """Return when a user's lockout ends, or None when they may try the key."""
        with self._lock, self._connect() as db:
            row = db.execute(
                "SELECT locked_until FROM access_attempts WHERE user_id=?", (user_id,)
            ).fetchone()
        if not row or not row["locked_until"]:
            return None
        until = datetime.fromisoformat(row["locked_until"])
        return until if until > datetime.now(UTC) else None

    def record_failure(self, user_id: int, *, limit: int, lock: timedelta) -> int:
        """Count one wrong key and return the attempts left, locking at zero.

        Reaching the limit starts a lockout and resets the counter, so the
        user gets a fresh set of attempts once it expires.
        """
        with self._lock, self._connect() as db:
            row = db.execute(
                "SELECT failures FROM access_attempts WHERE user_id=?", (user_id,)
            ).fetchone()
            failures = (row["failures"] if row else 0) + 1
            locked = None
            if failures >= limit:
                locked = (datetime.now(UTC) + lock).isoformat()
                failures = 0
            db.execute(
                """INSERT INTO access_attempts(user_id, failures, locked_until) VALUES(?,?,?)
                    ON CONFLICT(user_id) DO UPDATE SET
                        failures=excluded.failures, locked_until=excluded.locked_until""",
                (user_id, failures, locked),
            )
        return 0 if locked else limit - failures

    def set_consent(self, user_id: int, accepted: bool) -> None:
        """Record an authorized user's latest answer to the participation consent."""
        now = datetime.now(UTC).isoformat()
        with self._lock, self._connect() as db:
            db.execute(
                "UPDATE access SET consented_at=?, declined_at=? WHERE user_id=?",
                (now if accepted else None, None if accepted else now, user_id),
            )

    def consented_ids(self) -> list[int]:
        """List the users who hold the key and accepted to participate."""
        with self._lock, self._connect() as db:
            rows = db.execute(
                "SELECT user_id FROM access WHERE consented_at IS NOT NULL ORDER BY granted_at"
            ).fetchall()
        return [row[0] for row in rows]

    def announced(self, user_id: int, phase: str) -> bool:
        """Report whether a user was already told about a study phase."""
        with self._lock, self._connect() as db:
            row = db.execute(
                "SELECT 1 FROM announcements WHERE user_id=? AND phase=?", (user_id, phase)
            ).fetchone()
        return row is not None

    def mark_announced(self, user_id: int, phase: str) -> None:
        """Remember that a user already knows about a study phase."""
        with self._lock, self._connect() as db:
            db.execute(
                "INSERT OR IGNORE INTO announcements(user_id, phase, sent_at) VALUES(?,?,?)",
                (user_id, phase, datetime.now(UTC).isoformat()),
            )
