"""The generation queue: one worker thread runs the jobs StageCraft submits, in order.

One worker, because every job shares the process-wide Gemini quota and a simulated run already
spends a large part of a day's budget: running two at once would only make both wait. Each job
gets a fresh generator, and so a fresh provider and fresh settings, so an edit to .env takes
effect on the next job and no provider ever serves two runs.

A job is stopped through the pipeline's should_cancel, never by raising from a callback: the
pipeline checks it before every agent call, where a cancel cannot be mistaken for a provider
failure. The browser follows a job by polling its snapshot with the sequence number of the last
event it saw.
"""

from __future__ import annotations

import queue
import threading
import uuid
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, Protocol

from asg_stagecraft import GenerationOptions, StoryBrief
from asg_stagecraft.runtime.errors import ASGError, RunCancelledError
from pydantic import BaseModel, ConfigDict, model_validator

JobStatus = Literal["queued", "running", "completed", "failed", "cancelled"]
FINISHED: frozenset[str] = frozenset({"completed", "failed", "cancelled"})
# Events kept per job. A simulated run appends to a log file on every turn, and each append is
# an event: hundreds per run, which the browser does not need to keep forever.
EVENT_LIMIT = 400


class JobRequest(BaseModel):
    """What the interface asks to generate: a brief or a free prompt, and the run options."""

    model_config = ConfigDict(extra="forbid")

    mode: Literal["brief", "prompt"] = "brief"
    brief: StoryBrief | None = None
    prompt: str = ""
    options: GenerationOptions = GenerationOptions()

    @model_validator(mode="after")
    def one_source(self) -> JobRequest:
        """Require exactly the source the mode names."""
        if self.mode == "brief" and self.brief is None:
            raise ValueError("Falta la ficha de la obra.")
        if self.mode == "prompt" and not self.prompt.strip():
            raise ValueError("El prompt no puede estar vacío.")
        return self

    def story_request(self) -> StoryBrief | str:
        """Return what the generator is handed: the brief itself or the stripped prompt."""
        if self.mode == "brief":
            assert self.brief is not None
            return self.brief
        return self.prompt.strip()

    def title(self) -> str:
        """Name the job before the run has a title of its own."""
        if self.mode == "brief" and self.brief is not None:
            return self.brief.title or self.brief.plot[:60]
        return self.prompt.strip()[:60]


class GeneratorLike(Protocol):
    """The part of StoryGenerator a job uses; tests and the demo mode supply their own."""

    def generate(
        self,
        request: Any,
        on_progress: Callable | None = None,
        on_run_created: Callable | None = None,
        on_event: Callable | None = None,
        *,
        should_cancel: Callable[[], bool] | None = None,
    ) -> Any:
        """Generate one run and return an object with its run_dir."""


GeneratorFactory = Callable[[GenerationOptions], GeneratorLike]


@dataclass
class Job:
    """One requested generation and everything the browser is shown about it."""

    id: str
    request: JobRequest
    status: JobStatus = "queued"
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    finished_at: str | None = None
    run_dir: str | None = None
    progress: dict[str, Any] = field(
        default_factory=lambda: {"percent": 0, "stage": "queued", "description": "En cola"}
    )
    counters: dict[str, int] = field(default_factory=lambda: {"agents": 0, "turns": 0})
    events: deque = field(default_factory=lambda: deque(maxlen=EVENT_LIMIT))
    sequence: int = 0
    error: dict[str, Any] | None = None
    cancel_requested: bool = False

    def snapshot(self, since: int = 0) -> dict[str, Any]:
        """Describe the job, with only the events after a given sequence number."""
        return {
            "id": self.id,
            "status": self.status,
            "title": self.request.title(),
            "created_at": self.created_at,
            "finished_at": self.finished_at,
            "run_dir": self.run_dir,
            "run_id": Path(self.run_dir).name if self.run_dir else None,
            "collection": Path(self.run_dir).parent.name if self.run_dir else None,
            "progress": dict(self.progress),
            "counters": dict(self.counters),
            "error": self.error,
            "cancel_requested": self.cancel_requested,
            "story_format": self.request.options.story_format.value,
            "sequence": self.sequence,
            "events": [event for event in self.events if event["seq"] > since],
        }


class JobRunner:
    """Run submitted jobs one after another on a single worker thread."""

    def __init__(self, generator_factory: GeneratorFactory) -> None:
        """Keep the factory that builds one generator per job."""
        self.generator_factory = generator_factory
        self._jobs: dict[str, Job] = {}
        self._order: list[str] = []
        self._queue: queue.Queue[str | None] = queue.Queue()
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._idle = threading.Event()
        self._idle.set()

    def start(self) -> None:
        """Start the worker thread, once."""
        if self._thread is None:
            self._thread = threading.Thread(target=self._work, name="stagecraft-jobs", daemon=True)
            self._thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        """Cancel whatever runs, and wait a bounded time for the worker to leave."""
        with self._lock:
            for job in self._jobs.values():
                if job.status in {"queued", "running"}:
                    job.cancel_requested = True
        self._queue.put(None)
        if self._thread is not None:
            self._thread.join(timeout)
            self._thread = None

    def submit(self, request: JobRequest) -> dict[str, Any]:
        """Queue one generation and return its first snapshot."""
        job = Job(id=uuid.uuid4().hex[:12], request=request)
        with self._lock:
            self._jobs[job.id] = job
            self._order.append(job.id)
            self._idle.clear()
            snapshot = job.snapshot()
        self._queue.put(job.id)
        return snapshot

    def cancel(self, job_id: str) -> dict[str, Any] | None:
        """Withdraw a queued job, or ask a running one to stop at its next agent call."""
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None
            if job.status == "queued":
                self._finish(job, "cancelled")
                job.progress = {"percent": 0, "stage": "cancelled", "description": "Retirado"}
            elif job.status == "running":
                job.cancel_requested = True
                self._event(job, "cancel_requested", "Cancelación pedida", None)
            return job.snapshot()

    def snapshot(self, job_id: str, since: int = 0) -> dict[str, Any] | None:
        """Return one job as the browser sees it, or None when there is no such job."""
        with self._lock:
            job = self._jobs.get(job_id)
            return job.snapshot(since) if job else None

    def jobs(self) -> list[dict[str, Any]]:
        """Return every job, newest first, without their events."""
        with self._lock:
            return [
                {**self._jobs[job_id].snapshot(), "events": []} for job_id in reversed(self._order)
            ]

    def wait(self, timeout: float = 5.0) -> bool:
        """Block until no job is queued or running; tests use it."""
        return self._idle.wait(timeout)

    # -- the worker ----------------------------------------------------------------------

    def _work(self) -> None:
        """Take jobs off the queue until told to stop."""
        while True:
            job_id = self._queue.get()
            if job_id is None:
                return
            with self._lock:
                job = self._jobs.get(job_id)
                runnable = job is not None and job.status == "queued" and not job.cancel_requested
                if runnable:
                    job.status = "running"
                    job.progress = {"percent": 0, "stage": "analysis", "description": "Empezando"}
            if runnable:
                self._run(job)
            self._settle()

    def _settle(self) -> None:
        """Mark the runner idle once nothing waits or runs."""
        with self._lock:
            if all(job.status in FINISHED for job in self._jobs.values()):
                self._idle.set()

    def _run(self, job: Job) -> None:
        """Generate one job, turning every outcome into a status the browser can show."""
        try:
            generator = self.generator_factory(job.request.options)
            run = generator.generate(
                job.request.story_request(),
                on_progress=lambda update: self._progress(job, update),
                on_run_created=lambda path: self._created(job, path),
                on_event=lambda event: self._pipeline_event(job, event),
                should_cancel=lambda: job.cancel_requested,
            )
            with self._lock:
                job.run_dir = str(run.run_dir)
                job.progress = {"percent": 100, "stage": "completed", "description": "Terminada"}
                self._finish(job, "completed")
        except RunCancelledError:
            with self._lock:
                job.progress = {**job.progress, "description": "Cancelada"}
                self._finish(job, "cancelled")
        except ASGError as error:
            self._fail(job, error.code, error.summary, error.recommendations)
        except Exception as error:  # noqa: BLE001 - a job must never take the worker down
            self._fail(
                job,
                "UNEXPECTED_ERROR",
                "Ocurrió un error inesperado al generar.",
                [f"Detalle técnico: {type(error).__name__}."],
            )

    def _fail(self, job: Job, code: str, summary: str, recommendations: list[str]) -> None:
        """Record a failed job with a message fit for the interface."""
        with self._lock:
            job.error = {
                "code": code,
                "summary": summary,
                "recommendation": recommendations[0] if recommendations else "",
            }
            self._finish(job, "failed")

    def _finish(self, job: Job, status: JobStatus) -> None:
        """Close a job; the caller holds the lock."""
        job.status = status
        job.finished_at = datetime.now(UTC).isoformat()

    def _event(self, job: Job, kind: str, message: str, stage: str | None) -> None:
        """Append one event; the caller holds the lock."""
        job.sequence += 1
        job.events.append(
            {
                "seq": job.sequence,
                "kind": kind,
                "message": message,
                "stage": stage,
                "at": datetime.now(UTC).isoformat(),
            }
        )

    # -- callbacks, called on the worker thread ------------------------------------------

    def _progress(self, job: Job, update) -> None:
        """Keep the latest progress, except the transient quota waits, which become events."""
        with self._lock:
            if update.stage == "rate_limit":
                self._event(job, "rate_limit", update.description, job.progress.get("stage"))
                return
            job.progress = {
                "percent": update.percent,
                "stage": update.stage,
                "description": update.description,
                "chapter": update.chapter,
                "total": update.total_chapters,
            }

    def _created(self, job: Job, path) -> None:
        """Remember the run folder as soon as it exists, so a failure can still be opened."""
        with self._lock:
            job.run_dir = str(path)

    def _pipeline_event(self, job: Job, event) -> None:
        """Count agents and turns, and keep the events worth reading."""
        with self._lock:
            if event.kind == "agent_called":
                job.counters["agents"] += 1
            artifact = event.artifact or ""
            if artifact.endswith("turns.jsonl"):
                job.counters["turns"] += 1
            if event.kind in {"artifact_updated"} and artifact.endswith(".jsonl"):
                return
            self._event(job, event.kind, event.message, event.stage)
