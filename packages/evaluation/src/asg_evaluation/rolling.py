"""Durable rolling pools and lazily assigned reading sessions."""

from __future__ import annotations

import json
import random
import sqlite3
from pathlib import Path

from .catalog import catalog_snapshot, digest, guidance
from .pack import PACK_SESSION_SIZE
from .study_design import session_questions

GROWING_MODES = frozenset({"rolling", "pack"})


def _session_limit(mode: str) -> int:
    """Give rolling readers two sessions and pack readers a single one."""
    return 1 if mode == "pack" else 2


def backup_database(path: Path, target_version: int) -> None:
    """Back up an older SQLite database using its consistent online snapshot."""
    if not path.is_file() or not path.stat().st_size:
        return
    with sqlite3.connect(path) as source:
        version = source.execute("PRAGMA user_version").fetchone()[0]
        if version >= target_version:
            return
        destination = path.with_name(f"{path.name}.v{version}.bak")
        if not destination.exists():
            with sqlite3.connect(destination) as backup:
                source.backup(backup)


def migrate_rolling(db) -> None:
    """Add rolling state without changing existing fixed studies or their votes."""
    study_columns = {row[1] for row in db.execute("PRAGMA table_info(study)")}
    if "mode" not in study_columns:
        db.execute("ALTER TABLE study ADD COLUMN mode TEXT NOT NULL DEFAULT 'fixed'")
    if "revision" not in study_columns:
        db.execute("ALTER TABLE study ADD COLUMN revision INTEGER NOT NULL DEFAULT 0")
    if "active" not in {row[1] for row in db.execute("PRAGMA table_info(stories)")}:
        db.execute("ALTER TABLE stories ADD COLUMN active INTEGER NOT NULL DEFAULT 1")
    db.execute("DROP INDEX contribution_owner")
    db.execute(
        "CREATE UNIQUE INDEX contribution_owner ON stories(owner) "
        "WHERE owner IS NOT NULL AND curated=0 AND active=1"
    )
    db.execute(
        "CREATE TABLE IF NOT EXISTS first_contributions "
        "(participant TEXT PRIMARY KEY REFERENCES participants(id), "
        "story TEXT NOT NULL REFERENCES stories(id))"
    )
    db.execute(
        "CREATE TABLE IF NOT EXISTS sessions "
        "(participant TEXT REFERENCES participants(id), number INTEGER, "
        "revision INTEGER, seed INTEGER, pool TEXT NOT NULL, PRIMARY KEY(participant,number))"
    )
    db.execute(
        "CREATE TABLE IF NOT EXISTS publication_consent (participant TEXT PRIMARY KEY "
        "REFERENCES participants(id), allowed INTEGER NOT NULL)"
    )
    db.execute(
        "CREATE TABLE IF NOT EXISTS publications (story TEXT PRIMARY KEY REFERENCES stories(id), "
        "approved_at TEXT NOT NULL, synced_at TEXT, attempts INTEGER NOT NULL DEFAULT 0, "
        "next_attempt TEXT, error TEXT)"
    )


class RollingStudy:
    """Extend study storage with append-only pools and two bounded reading sessions."""

    def _require_enrollment(self, db, *, preparation: bool = True) -> dict:
        """Allow collection during evaluation only for a rolling study."""
        info = dict(db.execute("SELECT * FROM study").fetchone() or {})
        states = ["collection"]
        if preparation:
            states.append("preparation")
        if info.get("mode") in GROWING_MODES:
            states.append("evaluation")
        return self._require(db, *states)

    def collection_open(self) -> bool:
        """Report whether a new contribution may still be enrolled."""
        info = self.info()
        return info["state"] == "collection" or (
            info["mode"] in GROWING_MODES and info["state"] == "evaluation"
        )

    def _rolling_enrolled(self, db, sid: str, owner: str | None, curated: bool) -> None:
        """Count distinct first contributions and open voting once, atomically."""
        info = dict(db.execute("SELECT * FROM study").fetchone())
        if info["mode"] != "rolling":
            return
        db.execute("UPDATE study SET revision=revision+1")
        if owner and not curated:
            db.execute(
                "INSERT OR IGNORE INTO first_contributions SELECT id,? FROM participants "
                "WHERE id=? AND is_author=0",
                (sid, owner),
            )
        count = db.execute("SELECT COUNT(*) FROM first_contributions").fetchone()[0]
        if count >= 8 and info["state"] == "collection":
            snapshot = {
                "catalog": catalog_snapshot(),
                "guidance": guidance(),
                "seed": info["seed"],
                "mode": "rolling",
                "threshold": 8,
            }
            snapshot["sha256"] = digest(snapshot)
            db.execute(
                "UPDATE study SET state='evaluation',snapshot=?",
                (json.dumps(snapshot, ensure_ascii=False),),
            )

    def _ensure_session(self, db, participant: str) -> None:
        """Assign one reproducible session without rewriting earlier assignments."""
        info = dict(db.execute("SELECT * FROM study").fetchone())
        if info["mode"] not in GROWING_MODES or self._next(db, participant):
            return
        pack = info["mode"] == "pack"
        reader = db.execute("SELECT * FROM participants WHERE id=?", (participant,)).fetchone()
        if not reader or not reader["profile"]:
            return
        contributed = db.execute(
            "SELECT 1 FROM contributions WHERE participant=?"
            if pack
            else "SELECT 1 FROM first_contributions WHERE participant=?",
            (participant,),
        ).fetchone()
        if not contributed and not reader["is_author"]:
            return
        number = db.execute(
            "SELECT COALESCE(MAX(number),0)+1 FROM sessions WHERE participant=?", (participant,)
        ).fetchone()[0]
        if number > _session_limit(info["mode"]):
            return
        pool = self._eligible_session_pool(db, participant)
        if pack:
            members = {row[0] for row in db.execute("SELECT story FROM pack")}
            pool = [story for story in pool if story["id"] in members]
        if len(pool) < 2:
            return
        seed = int(digest([info["seed"], participant, number, info["revision"]])[:12], 16)
        rng = random.Random(seed)
        rng.shuffle(pool)
        pool.sort(key=lambda story: story["appearances"])
        chosen = [s["id"] for s in pool[:PACK_SESSION_SIZE]]
        db.execute(
            "INSERT INTO sessions VALUES (?,?,?,?,?)",
            (participant, number, info["revision"], seed, json.dumps(pool)),
        )
        questions = [
            {**q, "participant": participant, "session": number, "position": index}
            for index, q in enumerate(session_questions(chosen, rng), 1)
        ]
        self._insert_assignments(db, questions)

    @staticmethod
    def _eligible_session_pool(db, participant: str) -> list[dict]:
        """Exclude owned, known, retired and previously assigned stories."""
        return [
            dict(row)
            for row in db.execute(
                "SELECT s.id,s.text_hash,(SELECT COUNT(*) FROM assignments a WHERE a.void=0 "
                "AND (a.left_id=s.id OR a.right_id=s.id)) AS appearances FROM stories s "
                "WHERE s.active=1 AND (s.owner IS NULL OR s.owner<>?) AND NOT EXISTS "
                "(SELECT 1 FROM exposures e WHERE e.participant=? AND e.text_hash=s.text_hash) "
                "AND NOT EXISTS (SELECT 1 FROM assignments a WHERE a.participant=? "
                "AND (a.left_id=s.id OR a.right_id=s.id)) ORDER BY s.id",
                (participant, participant, participant),
            )
        ]

    def _replacement_pool(self, db, participant: str, session: int) -> list[dict]:
        """Replace recognized stories only from the session's recorded candidate pool."""
        row = db.execute(
            "SELECT pool FROM sessions WHERE participant=? AND number=?", (participant, session)
        ).fetchone()
        stories = self._stories(db)
        if row is None:
            return stories
        eligible = {story["id"] for story in json.loads(row[0])}
        return [story for story in stories if story["id"] in eligible]

    def session_waiting(self, participant: str) -> bool:
        """Distinguish a temporarily small pool from a completed two-session study."""
        with self.transaction() as db:
            count = db.execute(
                "SELECT COUNT(*) FROM sessions WHERE participant=?", (participant,)
            ).fetchone()[0]
        mode = self.info()["mode"]
        return mode in GROWING_MODES and count < _session_limit(mode)
