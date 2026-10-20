"""The first evaluation: each participant compares their own Top-Down and hybrid stories.

The tutor's method (docs/audio_2026-10-03, METODOLOGIA.md): people cannot score a story from
1 to 10, but they can say which of two they prefer, on three high-level criteria. Before the
blind study across participants exists, each person compares the two stories they made, one
per model, shown as A and B without saying which is which. The three questions are the study's
own (asg_evaluation.catalog), so these answers read the same way later.

A story enters at most one pair. Everything lives in SQLite, so a restart resumes the pair
where it stopped.
"""

from __future__ import annotations

import json
import random
import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

from asg_evaluation.catalog import guidance, questions

FORMATS = ("narrative", "simulated")
CHOICES = ("A", "B", "X")
_SCHEMA = (
    "CREATE TABLE IF NOT EXISTS pairs (id INTEGER PRIMARY KEY AUTOINCREMENT, "
    "user_id INTEGER NOT NULL, narrative_job INTEGER NOT NULL, simulated_job INTEGER NOT NULL, "
    "narrative_run TEXT NOT NULL, simulated_run TEXT NOT NULL, a_format TEXT NOT NULL, "
    "linked INTEGER NOT NULL, read_a INTEGER NOT NULL DEFAULT 0, "
    "read_b INTEGER NOT NULL DEFAULT 0, awaiting_reason TEXT, created_at TEXT NOT NULL, "
    "finished_at TEXT)",
    "CREATE TABLE IF NOT EXISTS answers (pair_id INTEGER NOT NULL, criterion TEXT NOT NULL, "
    "shown TEXT NOT NULL, choice TEXT NOT NULL, reason TEXT, answered_at TEXT NOT NULL, "
    "PRIMARY KEY (pair_id, criterion))",
)


def _now() -> str:
    """Return an ISO timestamp for audit columns."""
    return datetime.now(UTC).isoformat()


def criteria() -> list[tuple[str, str, str]]:
    """Return the tutor's three questions in order, as (id, question, what to look at)."""
    asked, look = questions(), guidance()
    return [(key, asked[key], look[key]) for key in sorted(asked)]


class OwnPairs:
    """Pair each participant's Top-Down and hybrid stories and keep their three answers."""

    def __init__(self, path: Path, *, rng: random.Random | None = None) -> None:
        """Open or create the database; the generator decides which story is shown as A."""
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.rng = rng or random.Random()
        for statement in _SCHEMA:
            self._run(statement)

    def _db(self) -> sqlite3.Connection:
        """Open a connection whose context manager commits or rolls back."""
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        return db

    def _run(self, sql: str, args: tuple = ()) -> list[sqlite3.Row]:
        """Execute one statement in its own transaction."""
        with closing(self._db()) as db, db:
            return db.execute(sql, args).fetchall()

    def open_pair(self, user_id: int) -> dict | None:
        """Return the participant's unfinished pair, if any."""
        rows = self._run(
            "SELECT * FROM pairs WHERE user_id=? AND finished_at IS NULL ORDER BY id LIMIT 1",
            (user_id,),
        )
        return self._view(dict(rows[0])) if rows else None

    def pair(self, pair_id: int) -> dict | None:
        """Return one pair with its progress."""
        rows = self._run("SELECT * FROM pairs WHERE id=?", (pair_id,))
        return self._view(dict(rows[0])) if rows else None

    def used_jobs(self, user_id: int) -> set[int]:
        """Return the jobs whose stories already belong to a pair."""
        rows = self._run(
            "SELECT narrative_job, simulated_job FROM pairs WHERE user_id=?", (user_id,)
        )
        return {job for row in rows for job in (row[0], row[1])}

    def candidate(self, user_id: int, completed: list[dict]) -> tuple[dict, dict, bool] | None:
        """Choose the two stories to compare, or None while one model is missing.

        A hybrid made from a Top-Down story's own idea is preferred: then the only difference
        between the two is the model. Otherwise the newest unpaired story of each model.
        """
        used = self.used_jobs(user_id)
        free = [job for job in completed if job["id"] not in used]
        by_id = {job["id"]: job for job in free}
        for job in free:
            source = by_id.get(job.get("source_job"))
            if source and {job["story_format"], source["story_format"]} == set(FORMATS):
                narrative, simulated = sorted((job, source), key=_format_order)
                return narrative, simulated, True
        newest = {}
        for job in free:
            newest.setdefault(job["story_format"], job)
        if set(newest) >= set(FORMATS):
            return newest["narrative"], newest["simulated"], False
        return None

    def create(self, user_id: int, narrative: dict, simulated: dict, linked: bool) -> dict:
        """Open a pair, choosing at random which story is shown as A."""
        a_format = self.rng.choice(FORMATS)
        with closing(self._db()) as db, db:
            cursor = db.execute(
                "INSERT INTO pairs(user_id,narrative_job,simulated_job,narrative_run,"
                "simulated_run,a_format,linked,created_at) VALUES (?,?,?,?,?,?,?,?)",
                (
                    user_id,
                    narrative["id"],
                    simulated["id"],
                    narrative["run_dir"],
                    simulated["run_dir"],
                    a_format,
                    int(linked),
                    _now(),
                ),
            )
        return self.pair(cursor.lastrowid)

    def mark_read(self, pair_id: int, side: str) -> dict:
        """Record that the participant read story A or B."""
        column = {"A": "read_a", "B": "read_b"}[side]
        self._run(f"UPDATE pairs SET {column}=1 WHERE id=?", (pair_id,))
        return self.pair(pair_id)

    def answer(self, pair_id: int, criterion: str, shown: str) -> dict:
        """Record the choice for the criterion being asked, then wait for an optional reason."""
        pair = self.pair(pair_id)
        if pair is None or pair["finished"]:
            raise ValueError("Esta comparación ya terminó.")
        if not pair["read"]:
            raise ValueError("Lee primero las dos historias.")
        if pair["next_criterion"] != criterion or shown not in CHOICES:
            raise ValueError("Esta pregunta ya no está activa.")
        choice = "abstain" if shown == "X" else pair["formats"][shown]
        with closing(self._db()) as db, db:
            db.execute(
                "INSERT INTO answers(pair_id,criterion,shown,choice,answered_at) "
                "VALUES (?,?,?,?,?)",
                (pair_id, criterion, shown, choice, _now()),
            )
            db.execute("UPDATE pairs SET awaiting_reason=? WHERE id=?", (criterion, pair_id))
        return self.pair(pair_id)

    def give_reason(self, pair_id: int, reason: str | None) -> dict:
        """Keep the participant's reason for the last answer, or none, and move on."""
        pair = self.pair(pair_id)
        if pair is None or not pair["awaiting_reason"]:
            raise ValueError("No hay ninguna respuesta pendiente de motivo.")
        with closing(self._db()) as db, db:
            if reason:
                db.execute(
                    "UPDATE answers SET reason=? WHERE pair_id=? AND criterion=?",
                    (reason.strip()[:1000], pair_id, pair["awaiting_reason"]),
                )
            db.execute("UPDATE pairs SET awaiting_reason=NULL WHERE id=?", (pair_id,))
            if len(pair["answers"]) == len(criteria()):
                db.execute("UPDATE pairs SET finished_at=? WHERE id=?", (_now(), pair_id))
        return self.pair(pair_id)

    def awaiting_reason(self, user_id: int) -> dict | None:
        """Return the pair that is waiting for this participant's reason, if any."""
        pair = self.open_pair(user_id)
        return pair if pair and pair["awaiting_reason"] else None

    def export(self) -> dict:
        """Every finished pair with its answers, by model rather than by letter."""
        pairs = [dict(row) for row in self._run("SELECT * FROM pairs ORDER BY id")]
        answers = [dict(row) for row in self._run("SELECT * FROM answers ORDER BY pair_id")]
        return {
            "criteria": {key: question for key, question, _ in criteria()},
            "pairs": [
                {
                    **{
                        key: pair[key]
                        for key in ("id", "user_id", "narrative_run", "simulated_run")
                    },
                    "a_format": pair["a_format"],
                    "same_idea": bool(pair["linked"]),
                    "finished_at": pair["finished_at"],
                    "answers": [
                        {key: item[key] for key in ("criterion", "choice", "reason")}
                        for item in answers
                        if item["pair_id"] == pair["id"]
                    ],
                }
                for pair in pairs
            ],
        }

    def export_json(self) -> str:
        """The export as indented JSON, for asg-telegram --export."""
        return json.dumps(self.export(), ensure_ascii=False, indent=2)

    def _view(self, row: dict) -> dict:
        """Add the derived progress of a pair: letters, answers and the next question."""
        answers = {
            item["criterion"]: dict(item)
            for item in self._run("SELECT * FROM answers WHERE pair_id=?", (row["id"],))
        }
        other = FORMATS[1] if row["a_format"] == FORMATS[0] else FORMATS[0]
        pending = [key for key, _, _ in criteria() if key not in answers]
        return {
            **row,
            "formats": {"A": row["a_format"], "B": other},
            "runs": {
                "A": row[f"{row['a_format']}_run"],
                "B": row[f"{other}_run"],
            },
            "read": bool(row["read_a"] and row["read_b"]),
            "answers": answers,
            "next_criterion": pending[0] if pending else None,
            "finished": row["finished_at"] is not None,
        }


def _format_order(job: dict) -> int:
    """Sort a narrative job before a simulated one."""
    return FORMATS.index(job["story_format"])
