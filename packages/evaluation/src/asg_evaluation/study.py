"""Transactional study storage independent of generators and messaging platforms."""

from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from .artifacts import load_json_object
from .catalog import catalog_snapshot, digest, guidance
from .study_design import coverage, make_assignments

SCHEMA_VERSION = 2
PROSE_FORMATS = {"baseline", "narrative", "simulated"}
_SCHEMA = (
    "CREATE TABLE study (id TEXT PRIMARY KEY, state TEXT NOT NULL, seed INTEGER NOT NULL, "
    "required_version TEXT NOT NULL, snapshot TEXT, created_at TEXT NOT NULL)",
    "CREATE TABLE participants (id TEXT PRIMARY KEY, external_id TEXT UNIQUE, "
    "profile TEXT NOT NULL DEFAULT '', is_author INTEGER NOT NULL DEFAULT 0, "
    "paused INTEGER NOT NULL DEFAULT 0)",
    "CREATE TABLE stories (id TEXT PRIMARY KEY, run_path TEXT UNIQUE NOT NULL, "
    "text TEXT NOT NULL, text_hash TEXT UNIQUE NOT NULL, provenance TEXT NOT NULL, "
    "owner TEXT REFERENCES participants(id), curated INTEGER NOT NULL DEFAULT 0, "
    "family TEXT NOT NULL)",
    "CREATE UNIQUE INDEX contribution_owner ON stories(owner) WHERE owner IS NOT NULL",
    "CREATE TABLE exposures (participant TEXT REFERENCES participants(id), text_hash TEXT, "
    "PRIMARY KEY(participant,text_hash))",
    "CREATE TABLE contributions (participant TEXT PRIMARY KEY REFERENCES participants(id), "
    "job_id TEXT, pending INTEGER NOT NULL DEFAULT 1)",
    "CREATE TABLE assignments (id TEXT PRIMARY KEY, participant TEXT REFERENCES participants(id), "
    "session INTEGER, position INTEGER, criterion TEXT, left_id TEXT REFERENCES stories(id), "
    "right_id TEXT REFERENCES stories(id), issued_at TEXT, void INTEGER NOT NULL DEFAULT 0)",
    "CREATE TABLE readings (participant TEXT REFERENCES participants(id), story TEXT REFERENCES "
    "stories(id), PRIMARY KEY(participant,story))",
    "CREATE TABLE votes (assignment TEXT PRIMARY KEY REFERENCES assignments(id), choice TEXT "
    "CHECK(choice IN ('A','B','abstain')), seconds REAL, created_at TEXT NOT NULL)",
)


def now() -> str:
    """Return a timezone-aware audit timestamp."""
    return datetime.now(UTC).isoformat()


def identifier(prefix: str) -> str:
    """Create an opaque identifier safe for short callback payloads."""
    return prefix + uuid.uuid4().hex[:16]


def read_candidate(directory: str | Path) -> dict:
    """Validate a completed prose run without importing its generator's schema."""
    directory = Path(directory).resolve()
    text = (directory / "story.md").read_text(encoding="utf-8")
    metadata = load_json_object(directory / "metadata.json")
    options = load_json_object(directory / "generation_options.json")
    version = load_json_object(directory / "generator_version.json")
    request = load_json_object(directory / "request.json")
    fmt = options.get("story_format", metadata.get("story_format"))
    if metadata.get("status") != "completed" or fmt not in PROSE_FORMATS or not text.strip():
        raise ValueError("El estudio admite únicamente historias completas en prosa.")
    provenance = {
        "metadata": metadata,
        "options": options,
        "version": version,
        "request": request,
        "source": load_json_object(directory / "source_run.json"),
    }
    return {
        "run_path": str(directory),
        "text": text,
        "text_hash": digest(text),
        "provenance": provenance,
        "family": digest(request.get("original_prompt", text)),
    }


class StudyRepository:
    """Keep one study and all its snapshots, participants and votes in SQLite."""

    def __init__(self, path: str | Path) -> None:
        """Open an existing study or initialize its versioned schema."""
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.transaction() as db:
            version = db.execute("PRAGMA user_version").fetchone()[0]
            if version > SCHEMA_VERSION:
                raise ValueError("La base del estudio usa una versión más reciente.")
            if version == 0:
                for statement in _SCHEMA:
                    db.execute(statement)
            if version < 2:
                db.execute("DROP INDEX contribution_owner")
                db.execute(
                    "CREATE UNIQUE INDEX contribution_owner ON stories(owner) "
                    "WHERE owner IS NOT NULL AND curated=0"
                )
                db.execute(f"PRAGMA user_version={SCHEMA_VERSION}")

    @contextmanager
    def transaction(self):
        """Serialize writes across threads and processes and roll back failed operations."""
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def create(self, study_id: str, *, required_version: str, seed: int = 42) -> None:
        """Create a preparation-stage study pinned to a future generator release."""
        if not required_version.strip() or not study_id.strip():
            raise ValueError("Indica el estudio y la versión definitiva del generador.")
        with self.transaction() as db:
            if db.execute("SELECT 1 FROM study").fetchone():
                raise ValueError("Esta base ya contiene un estudio.")
            db.execute(
                "INSERT INTO study VALUES (?,?,?,?,?,?)",
                (study_id, "preparation", seed, required_version, None, now()),
            )

    def info(self) -> dict:
        """Read the public lifecycle configuration."""
        with self.transaction() as db:
            row = db.execute("SELECT * FROM study").fetchone()
        if row is None:
            raise ValueError("Primero crea el estudio con evaluation-study create.")
        result = dict(row)
        result["snapshot"] = json.loads(result["snapshot"]) if result["snapshot"] else None
        return result

    @staticmethod
    def _require(db, *states: str) -> dict:
        """Enforce lifecycle transitions inside the same transaction as a mutation."""
        row = db.execute("SELECT * FROM study").fetchone()
        if row is None or row["state"] not in states:
            raise ValueError("La operación no está disponible en esta fase del estudio.")
        return dict(row)

    def transition(self, state: str) -> None:
        """Advance collection, voting or closure; freezing has its own validated operation."""
        previous = {"collection": "preparation", "evaluation": "frozen", "closed": "evaluation"}
        if state not in previous:
            raise ValueError("Transición desconocida.")
        with self.transaction() as db:
            self._require(db, previous[state])
            db.execute("UPDATE study SET state=?", (state,))

    def participant(self, external_id: str, *, profile: str = "", is_author: bool = False) -> dict:
        """Register a pseudonym during collection or recover an existing participant."""
        with self.transaction() as db:
            row = db.execute(
                "SELECT * FROM participants WHERE external_id=?", (str(external_id),)
            ).fetchone()
            if row is None:
                self._require(db, "preparation", "collection")
                pid = identifier("p")
                db.execute(
                    "INSERT INTO participants(id,external_id,profile,is_author) VALUES (?,?,?,?)",
                    (pid, str(external_id), profile, int(is_author)),
                )
            else:
                pid = row["id"]
                if is_author and not row["is_author"]:
                    self._require(db, "preparation", "collection")
                    db.execute("UPDATE participants SET is_author=1 WHERE id=?", (pid,))
                if profile and profile != row["profile"]:
                    self._require(db, "preparation", "collection")
                    db.execute("UPDATE participants SET profile=? WHERE id=?", (profile, pid))
            return dict(db.execute("SELECT * FROM participants WHERE id=?", (pid,)).fetchone())

    def add_story(
        self,
        directory: str | Path,
        *,
        owner: str | None = None,
        curated: bool = False,
        family: str | None = None,
    ) -> str:
        """Enroll or replace one contribution before freeze, preserving its stable identifier."""
        candidate = read_candidate(directory)
        with self.transaction() as db:
            self._require(db, "preparation", "collection")
            existing = db.execute(
                "SELECT * FROM stories WHERE run_path=?", (candidate["run_path"],)
            ).fetchone()
            if existing and (existing["owner"] != owner or bool(existing["curated"]) != curated):
                raise ValueError("El run ya tiene otra procedencia inscrita.")
            old = existing or (
                db.execute(
                    "SELECT id FROM stories WHERE owner=? AND curated=0", (owner,)
                ).fetchone()
                if owner and not curated
                else None
            )
            sid = old["id"] if old else identifier("s")
            if old:
                db.execute("DELETE FROM stories WHERE id=?", (sid,))
            db.execute(
                "INSERT INTO stories VALUES (?,?,?,?,?,?,?,?)",
                (
                    sid,
                    candidate["run_path"],
                    candidate["text"],
                    candidate["text_hash"],
                    json.dumps(candidate["provenance"], ensure_ascii=False),
                    owner,
                    int(curated),
                    family or candidate["family"],
                ),
            )
            if owner:
                db.execute(
                    "INSERT OR IGNORE INTO exposures VALUES (?,?)", (owner, candidate["text_hash"])
                )
        return sid

    @staticmethod
    def _stories(db) -> list[dict]:
        """Decode immutable text and provenance records."""
        result = [dict(row) for row in db.execute("SELECT * FROM stories ORDER BY id")]
        for row in result:
            row["provenance"] = json.loads(row["provenance"])
        return result

    def freeze(self) -> dict:
        """Validate the roster and corpus, then atomically freeze snapshots and assignments."""
        with self.transaction() as db:
            info = self._require(db, "collection")
            stories = self._stories(db)
            readers = [dict(r) for r in db.execute("SELECT * FROM participants ORDER BY id")]
            self._validate_pool(stories, readers, info["required_version"])
            exposures = {
                (r[0], r[1])
                for r in db.execute(
                    "SELECT e.participant,s.id FROM exposures e "
                    "JOIN stories s ON e.text_hash=s.text_hash"
                )
            }
            assignments = make_assignments(stories, readers, exposures, info["seed"])
            snapshot = {
                "catalog": catalog_snapshot(),
                "guidance": guidance(),
                "seed": info["seed"],
                "required_version": info["required_version"],
                "stories": [
                    {k: s[k] for k in ("id", "text_hash", "provenance", "owner", "family")}
                    for s in stories
                ],
                "participants": [
                    {k: r[k] for k in ("id", "profile", "is_author")} for r in readers
                ],
                "assignments": assignments,
            }
            snapshot["sha256"] = digest(snapshot)
            self._insert_assignments(db, assignments)
            db.execute(
                "UPDATE study SET state='frozen', snapshot=?",
                (json.dumps(snapshot, ensure_ascii=False),),
            )
        return snapshot

    @staticmethod
    def _validate_pool(stories: list[dict], readers: list[dict], version: str) -> None:
        """Reject incomplete, changed or mixed-version experimental inputs."""
        curated = [s for s in stories if s["curated"]]
        baselines = [
            s for s in curated if s["provenance"]["metadata"].get("story_format") == "baseline"
        ]
        if len(curated) != 5 or len(baselines) != 2 or len(readers) < 2:
            raise ValueError(
                "Se requieren cinco historias seleccionadas, dos líneas base "
                "y al menos dos lectores."
            )
        if any(not r["profile"] for r in readers):
            raise ValueError("Falta el perfil lector de algún participante.")
        for story in stories:
            current = read_candidate(story["run_path"])
            if (
                current["text_hash"] != story["text_hash"]
                or current["provenance"] != story["provenance"]
            ):
                raise ValueError(
                    "Un run cambió desde su inscripción; inscríbelo de nuevo antes del cierre."
                )
            if story["provenance"]["version"].get("generator_version") != version:
                raise ValueError(
                    "Todas las historias deben usar la versión fijada para el estudio."
                )

    @staticmethod
    def _insert_assignments(db, assignments: list[dict]) -> None:
        """Persist short opaque question identifiers independent of story paths."""
        for q in assignments:
            db.execute(
                "INSERT INTO assignments(id,participant,session,position,criterion,"
                "left_id,right_id) "
                "VALUES (?,?,?,?,?,?,?)",
                (
                    identifier("q"),
                    q["participant"],
                    q["session"],
                    q["position"],
                    q["criterion"],
                    q["left"],
                    q["right"],
                ),
            )

    def pause(self, participant: str, paused: bool = True) -> None:
        """Persist a reader's pause independently from generation conversation state."""
        with self.transaction() as db:
            db.execute("UPDATE participants SET paused=? WHERE id=?", (int(paused), participant))

    @staticmethod
    def _next(db, participant: str):
        """Find the first unanswered active question in session order."""
        return db.execute(
            "SELECT a.*,a.left_id AS 'left',a.right_id AS 'right' FROM assignments a "
            "LEFT JOIN votes v ON v.assignment=a.id WHERE a.participant=? AND a.void=0 "
            "AND v.assignment IS NULL ORDER BY a.session,a.position LIMIT 1",
            (participant,),
        ).fetchone()

    def next_question(self, participant: str) -> dict | None:
        """Issue the next question with blinded story payloads only."""
        with self.transaction() as db:
            self._require(db, "evaluation")
            reader = db.execute(
                "SELECT paused FROM participants WHERE id=?", (participant,)
            ).fetchone()
            if reader is None or reader["paused"]:
                return None
            row = self._next(db, participant)
            if row is None:
                return None
            if not row["issued_at"]:
                db.execute("UPDATE assignments SET issued_at=? WHERE id=?", (now(), row["id"]))
            result = dict(row)
            for side in ("left", "right"):
                story = db.execute(
                    "SELECT id,text FROM stories WHERE id=?", (row[side],)
                ).fetchone()
                read = db.execute(
                    "SELECT 1 FROM readings WHERE participant=? AND story=?",
                    (participant, story["id"]),
                ).fetchone()
                result[side] = {"id": story["id"], "text": story["text"], "read": bool(read)}
            return result

    def mark_read(self, participant: str, question: str, story: str) -> None:
        """Acknowledge delivery only for a story in the reader's active question."""
        with self.transaction() as db:
            self._require(db, "evaluation")
            row = self._next(db, participant)
            if row is None or row["id"] != question or story not in (row["left"], row["right"]):
                raise ValueError("Esta lectura ya no está activa.")
            db.execute("INSERT OR IGNORE INTO readings VALUES (?,?)", (participant, story))

    def vote(self, participant: str, question: str, choice: str) -> bool:
        """Atomically validate ownership, active question and reading before saving a vote."""
        if choice not in {"A", "B", "abstain"}:
            raise ValueError("Respuesta desconocida.")
        with self.transaction() as db:
            self._require(db, "evaluation")
            old = db.execute(
                "SELECT a.participant FROM votes v JOIN assignments a ON a.id=v.assignment "
                "WHERE v.assignment=?",
                (question,),
            ).fetchone()
            if old:
                if old[0] != participant:
                    raise ValueError("Esta pregunta pertenece a otro lector.")
                return False
            row = self._next(db, participant)
            paused = db.execute(
                "SELECT paused FROM participants WHERE id=?", (participant,)
            ).fetchone()
            if row is None or row["id"] != question or not paused or paused[0]:
                raise ValueError("Esta pregunta ya no está activa.")
            reads = db.execute(
                "SELECT COUNT(*) FROM readings WHERE participant=? AND story IN (?,?)",
                (participant, row["left"], row["right"]),
            ).fetchone()[0]
            if reads != 2 or not row["issued_at"]:
                raise ValueError("Confirma primero la lectura de ambas historias.")
            seconds = max(
                0, (datetime.now(UTC) - datetime.fromisoformat(row["issued_at"])).total_seconds()
            )
            db.execute("INSERT INTO votes VALUES (?,?,?,?)", (question, choice, seconds, now()))
        return True

    def recognize(self, participant: str, question: str, story: str) -> None:
        """Exclude a known story and replace its unvoted appearances without erasing votes."""
        with self.transaction() as db:
            self._require(db, "evaluation")
            current = self._next(db, participant)
            if (
                current is None
                or current["id"] != question
                or story not in (current["left"], current["right"])
            ):
                raise ValueError("Esta pregunta ya no está activa.")
            if db.execute(
                "SELECT 1 FROM readings WHERE participant=? AND story=?", (participant, story)
            ).fetchone():
                raise ValueError("Indica si conoces el relato antes de confirmar su lectura.")
            row = db.execute("SELECT text_hash FROM stories WHERE id=?", (story,)).fetchone()
            db.execute("INSERT OR IGNORE INTO exposures VALUES (?,?)", (participant, row[0]))
            assigned = {
                r[0]
                for r in db.execute(
                    "SELECT left_id FROM assignments WHERE participant=? UNION "
                    "SELECT right_id FROM assignments WHERE participant=?",
                    (participant, participant),
                )
            }
            available = [
                s
                for s in self._stories(db)
                if s["id"] not in assigned
                and s["owner"] != participant
                and not db.execute(
                    "SELECT 1 FROM exposures WHERE participant=? AND text_hash=?",
                    (participant, s["text_hash"]),
                ).fetchone()
            ]
            affected = db.execute(
                "SELECT * FROM assignments WHERE participant=? AND void=0 AND "
                "(left_id=? OR right_id=?) AND id NOT IN (SELECT assignment FROM votes)",
                (participant, story, story),
            ).fetchall()
            for q in affected:
                db.execute("UPDATE assignments SET void=1 WHERE id=?", (q["id"],))
                if available:
                    self._insert_assignments(
                        db,
                        [
                            {
                                "participant": participant,
                                "session": q["session"],
                                "position": q["position"],
                                "criterion": q["criterion"],
                                "left": available[0]["id"]
                                if q["left_id"] == story
                                else q["left_id"],
                                "right": available[0]["id"]
                                if q["right_id"] == story
                                else q["right_id"],
                            }
                        ],
                    )

    def request_contribution(self, participant: str) -> None:
        """Reserve the next generation as this participant's contribution."""
        with self.transaction() as db:
            self._require(db, "collection")
            db.execute(
                "INSERT INTO contributions VALUES (?,NULL,1) ON CONFLICT(participant) "
                "DO UPDATE SET job_id=NULL,pending=1",
                (participant,),
            )

    def bind_contribution(self, external_id: str, job_id: str) -> None:
        """Bind a pending contribution to a durable generation job."""
        with self.transaction() as db:
            db.execute(
                "UPDATE contributions SET job_id=? WHERE pending=1 AND job_id IS NULL AND "
                "participant=(SELECT id FROM participants WHERE external_id=?)",
                (job_id, str(external_id)),
            )

    def release_contribution(self, external_id: str, job_id: str) -> None:
        """Unbind a reservation whose job failed, so the next attempt can claim it."""
        with self.transaction() as db:
            db.execute(
                "UPDATE contributions SET job_id=NULL WHERE pending=1 AND job_id=? AND "
                "participant=(SELECT id FROM participants WHERE external_id=?)",
                (job_id, str(external_id)),
            )

    def find_participant(self, external_id: str) -> dict | None:
        """Look up a participant without registering one."""
        with self.transaction() as db:
            row = db.execute(
                "SELECT * FROM participants WHERE external_id=?", (str(external_id),)
            ).fetchone()
        return dict(row) if row else None

    def contribution(self, participant: str) -> dict:
        """Report whether a contribution is enrolled and whether another one is reserved."""
        with self.transaction() as db:
            enrolled = db.execute(
                "SELECT 1 FROM stories WHERE owner=? AND curated=0", (participant,)
            ).fetchone()
            pending = db.execute(
                "SELECT 1 FROM contributions WHERE participant=? AND pending=1", (participant,)
            ).fetchone()
        return {"enrolled": bool(enrolled), "pending": bool(pending)}

    def progress(self, participant: str) -> dict:
        """Count answered and planned active questions, overall and per session."""
        with self.transaction() as db:
            rows = db.execute(
                "SELECT a.session, COUNT(*) AS total, COUNT(v.assignment) AS answered "
                "FROM assignments a LEFT JOIN votes v ON v.assignment=a.id "
                "WHERE a.participant=? AND a.void=0 GROUP BY a.session",
                (participant,),
            ).fetchall()
        return {
            "answered": sum(row["answered"] for row in rows),
            "total": sum(row["total"] for row in rows),
            "sessions": len(rows),
            "answered_by_session": {row["session"]: row["answered"] for row in rows},
        }

    def participant_ids(self) -> list[str]:
        """List the external identifiers of participants with a reader profile."""
        with self.transaction() as db:
            rows = db.execute(
                "SELECT external_id FROM participants WHERE profile<>'' AND external_id IS NOT NULL"
            ).fetchall()
        return [row[0] for row in rows]

    def complete_generation(self, external_id: str, job_id: str | None, directory: Path) -> bool:
        """Record exposure and enroll only the job explicitly reserved for contribution."""
        with self.transaction() as db:
            participant = db.execute(
                "SELECT id FROM participants WHERE external_id=?", (str(external_id),)
            ).fetchone()
            if not participant:
                return False
            pid = participant[0]
            text = (directory / "story.md").read_text(encoding="utf-8")
            db.execute("INSERT OR IGNORE INTO exposures VALUES (?,?)", (pid, digest(text)))
            pending = db.execute(
                "SELECT 1 FROM contributions WHERE participant=? AND pending=1 AND job_id=?",
                (pid, job_id),
            ).fetchone()
        if not pending:
            return False
        self.add_story(directory, owner=pid)
        with self.transaction() as db:
            db.execute(
                "UPDATE contributions SET pending=0 WHERE participant=? AND job_id=?", (pid, job_id)
            )
        return True

    def export(self) -> dict:
        """Export pseudonymous research data without external account IDs or local paths."""
        with self.transaction() as db:
            stories = self._stories(db)
            for story in stories:
                story.pop("run_path")
            readers = [
                dict(r)
                for r in db.execute("SELECT id,profile,is_author FROM participants ORDER BY id")
            ]
            assignments = [
                dict(r)
                for r in db.execute(
                    "SELECT id,participant,session,position,criterion,"
                    "left_id AS 'left',right_id AS 'right',void FROM assignments "
                    "ORDER BY participant,session,position"
                )
            ]
            votes = [
                dict(r)
                for r in db.execute(
                    "SELECT a.id,a.participant,a.session,a.criterion,"
                    "a.left_id AS 'left',a.right_id AS 'right',v.choice,v.seconds,v.created_at "
                    "FROM votes v JOIN assignments a ON a.id=v.assignment ORDER BY v.created_at"
                )
            ]
        return {
            "schema_version": SCHEMA_VERSION,
            "study": self.info(),
            "stories": stories,
            "participants": readers,
            "assignments": assignments,
            "votes": votes,
            "coverage": coverage([s["id"] for s in stories], assignments, votes),
        }
