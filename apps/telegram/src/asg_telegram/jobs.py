"""Durable FIFO of story requests and the single worker that generates and delivers them."""

from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

from .delivery import send_retrying, send_story
from .generator import METHODS, GenerationCancelled, GenerationFailure, StoryOutline

LOGGER = logging.getLogger(__name__)
ACTIVE = ("queued", "running")
MAX_ATTEMPTS = 2
PROGRESS_SECONDS = 5.0
_SCHEMA = (
    "CREATE TABLE IF NOT EXISTS jobs (id INTEGER PRIMARY KEY AUTOINCREMENT, "
    "chat_id INTEGER NOT NULL, user_id INTEGER NOT NULL, story_format TEXT NOT NULL, "
    "prompt TEXT, brief TEXT, status TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0, "
    "cancel INTEGER NOT NULL DEFAULT 0, run_dir TEXT, error TEXT, "
    "created_at TEXT NOT NULL, updated_at TEXT NOT NULL)"
)


def _now() -> str:
    """Return an ISO timestamp for audit columns."""
    return datetime.now(UTC).isoformat()


class JobQueue:
    """One generation at a time, in arrival order, surviving restarts."""

    def __init__(self, path: Path) -> None:
        """Open or create the queue database."""
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._run(_SCHEMA)

    def _db(self) -> sqlite3.Connection:
        """Open a connection whose context manager commits or rolls back."""
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        return db

    def _run(self, sql: str, args: tuple = ()) -> list[sqlite3.Row]:
        """Execute one statement in its own transaction."""
        with closing(self._db()) as db, db:
            return db.execute(sql, args).fetchall()

    def enqueue(
        self, chat_id: int, user_id: int, story_format: str, request: str | StoryOutline
    ) -> int:
        """Queue a request; one active request per participant."""
        if story_format not in METHODS:
            raise ValueError("Método desconocido.")
        with closing(self._db()) as db, db:
            if db.execute(
                "SELECT 1 FROM jobs WHERE user_id=? AND status IN (?,?)", (user_id, *ACTIVE)
            ).fetchone():
                raise ValueError("Ya tienes una historia en marcha. Espera a que llegue.")
            prompt, brief = (
                (None, json.dumps(request.to_dict(), ensure_ascii=False))
                if isinstance(request, StoryOutline)
                else (request, None)
            )
            cursor = db.execute(
                "INSERT INTO jobs(chat_id,user_id,story_format,prompt,brief,status,created_at,"
                "updated_at) VALUES (?,?,?,?,?,'queued',?,?)",
                (chat_id, user_id, story_format, prompt, brief, _now(), _now()),
            )
            return cursor.lastrowid

    def ahead(self, job_id: int) -> int:
        """Count the requests that will run before this one."""
        return self._run(
            "SELECT COUNT(*) FROM jobs WHERE status IN (?,?) AND id<?", (*ACTIVE, job_id)
        )[0][0]

    def claim(self) -> dict | None:
        """Mark the oldest queued request as running and return it."""
        with closing(self._db()) as db, db:
            row = db.execute(
                "SELECT * FROM jobs WHERE status='queued' ORDER BY id LIMIT 1"
            ).fetchone()
            if row is None:
                return None
            db.execute(
                "UPDATE jobs SET status='running', attempts=attempts+1, updated_at=? WHERE id=?",
                (_now(), row["id"]),
            )
        job = dict(row)
        job["request"] = (
            StoryOutline.from_dict(json.loads(job["brief"])) if job["brief"] else job["prompt"]
        )
        return job

    def finish(self, job_id: int, status: str, *, run_dir: Path | None = None, error=None):
        """Close a request as completed, failed or cancelled."""
        self._run(
            "UPDATE jobs SET status=?, run_dir=?, error=?, updated_at=? WHERE id=?",
            (status, str(run_dir) if run_dir else None, error, _now(), job_id),
        )

    def cancel(self, user_id: int) -> str | None:
        """Cancel the participant's active request: at once if queued, cooperatively if running."""
        with closing(self._db()) as db, db:
            row = db.execute(
                "SELECT id,status FROM jobs WHERE user_id=? AND status IN (?,?)", (user_id, *ACTIVE)
            ).fetchone()
            if row is None:
                return None
            if row["status"] == "queued":
                db.execute("UPDATE jobs SET status='cancelled' WHERE id=?", (row["id"],))
            else:
                db.execute("UPDATE jobs SET cancel=1 WHERE id=?", (row["id"],))
            return row["status"]

    def attach_run(self, job_id: int, run_dir: Path) -> None:
        """Remember the run directory a job is writing, so a restart can close it."""
        self._run(
            "UPDATE jobs SET run_dir=?, updated_at=? WHERE id=?", (str(run_dir), _now(), job_id)
        )

    def cancel_requested(self, job_id: int) -> bool:
        """Tell the running pipeline whether its participant asked to stop."""
        return bool(self._run("SELECT cancel FROM jobs WHERE id=?", (job_id,))[0][0])

    def recover(self) -> list[dict]:
        """After a restart, requeue interrupted runs once and fail the rest."""
        with closing(self._db()) as db, db:
            rows = [dict(r) for r in db.execute("SELECT * FROM jobs WHERE status='running'")]
            for row in rows:
                retry = row["attempts"] < MAX_ATTEMPTS and not row["cancel"]
                row["status"] = "queued" if retry else "failed"
                db.execute(
                    "UPDATE jobs SET status=?, error=?, updated_at=? WHERE id=?",
                    (row["status"], None if retry else "Interrumpida", _now(), row["id"]),
                )
        return rows


class StoryWorker:
    """Generate queued stories one by one, deliver them and enroll them in the study."""

    def __init__(self, bot, queue: JobQueue, generator, study) -> None:
        """Wire the worker to the bot, the queue, the generator and the study."""
        self.bot = bot
        self.queue = queue
        self.generator = generator
        self.study = study
        self._wake = asyncio.Event()

    def wake(self) -> None:
        """Signal that a new request is waiting."""
        self._wake.set()

    async def run(self) -> None:
        """Process the queue forever; a failing job never stops the worker."""
        for job in self.queue.recover():
            if job.get("run_dir"):
                # The interrupted run would stay "running" forever: the retry writes a new one.
                await asyncio.to_thread(self.generator.close_interrupted, Path(job["run_dir"]))
            text = (
                "El bot se reinició: tu historia vuelve a la cola."
                if job["status"] == "queued"
                else "El bot se reinició dos veces con tu historia; pídela de nuevo con /crear."
            )
            await send_retrying(
                lambda job=job, text=text: self.bot.send_message(chat_id=job["chat_id"], text=text),
                "el aviso de reinicio",
            )
        while True:
            job = self.queue.claim()
            if job is None:
                await self._wake.wait()
                self._wake.clear()
                continue
            try:
                await self.process(job)
            except Exception:
                LOGGER.exception("Fallo inesperado en el trabajo %s", job["id"])
                self.queue.finish(job["id"], "failed", error="Error interno")

    async def process(self, job: dict) -> None:
        """Generate one story, keeping a single progress message up to date."""
        chat = job["chat_id"]
        message = await self.bot.send_message(chat_id=chat, text="⏳ Generando tu historia… 0 %")
        latest = {"text": "", "shown": "", "at": 0.0}

        def on_progress(percent: int, description: str) -> None:
            """Remember the latest milestone; the event loop shows it."""
            latest["text"] = f"⏳ {description}… {percent} %"

        async def refresh() -> None:
            """Edit the progress message at most every few seconds."""
            while True:
                await asyncio.sleep(PROGRESS_SECONDS)
                if latest["text"] and latest["text"] != latest["shown"]:
                    latest["shown"] = latest["text"]
                    await send_retrying(lambda: message.edit_text(latest["shown"]), "el progreso")

        ticker = asyncio.create_task(refresh())
        try:
            run_dir = await asyncio.to_thread(
                self.generator.generate,
                job["request"],
                job["story_format"],
                on_progress=on_progress,
                should_cancel=lambda: self.queue.cancel_requested(job["id"]),
                on_run_created=lambda run_dir: self.queue.attach_run(job["id"], run_dir),
            )
        except GenerationCancelled:
            self.queue.finish(job["id"], "cancelled")
            await self.bot.send_message(chat_id=chat, text="Generación cancelada.")
            return
        except GenerationFailure as failure:
            self.queue.finish(job["id"], "failed", error=failure.summary)
            hint = " Se acabó la cuota del modelo; prueba más tarde." if failure.quota else ""
            await self.bot.send_message(chat_id=chat, text=f"❌ {failure.summary}{hint}")
            return
        finally:
            ticker.cancel()
        self.queue.finish(job["id"], "completed", run_dir=run_dir)
        await send_retrying(lambda: message.edit_text("✅ Historia terminada."), "el progreso")
        await send_story(self.bot, chat, run_dir, heading="Tu historia")
        await self.bot.send_message(chat_id=chat, text=self._enroll(job, run_dir))

    def _enroll(self, job: dict, run_dir: Path) -> str:
        """Add the story to the study while it collects stories, and say so."""
        try:
            owner = self.study.participant(str(job["user_id"]))
            self.study.add_story(run_dir, owner=owner)
        except ValueError as exc:
            LOGGER.info("Historia %s fuera del estudio: %s", run_dir.name, exc)
            return "Gracias. Puedes crear otra con /crear o votar con /evaluar."
        return "Gracias: tu historia entra en el estudio. Crea otra con /crear."
