"""Blind pairwise study storage, independent of generators and messaging platforms.

One study lives in one SQLite file and goes through three phases: collection (stories are
enrolled), evaluation (the pool is frozen and readers compare pairs) and closed. Questions are
assigned lazily, one at a time, so anyone may vote without a roster prepared in advance.
"""

from __future__ import annotations

import json
import random
import sqlite3
import uuid
from collections import Counter
from contextlib import contextmanager
from datetime import UTC, datetime
from itertools import combinations
from pathlib import Path

from .artifacts import load_json_object
from .catalog import CRITERIA, catalog_snapshot, digest, guidance, questions
from .preferences import components

# The retired fixed, rolling and pack studies used schemas 1-4; their files stay as data.
SCHEMA_VERSION = 10
PROSE_FORMATS = {"baseline", "narrative", "simulated"}
QUESTIONS_PER_READER = 15
MIN_POOL = 3
_SCHEMA = (
    "CREATE TABLE study (id TEXT PRIMARY KEY, state TEXT NOT NULL, seed INTEGER NOT NULL, "
    "snapshot TEXT, created_at TEXT NOT NULL, opened_at TEXT, closed_at TEXT)",
    "CREATE TABLE participants (id TEXT PRIMARY KEY, external_id TEXT UNIQUE NOT NULL, "
    "is_author INTEGER NOT NULL DEFAULT 0)",
    "CREATE TABLE stories (id TEXT PRIMARY KEY, run_path TEXT UNIQUE NOT NULL, "
    "text TEXT NOT NULL, text_hash TEXT UNIQUE NOT NULL, provenance TEXT NOT NULL, "
    "owner TEXT REFERENCES participants(id), family TEXT NOT NULL, "
    "excluded INTEGER NOT NULL DEFAULT 0)",
    "CREATE TABLE known (participant TEXT REFERENCES participants(id), "
    "story TEXT REFERENCES stories(id), PRIMARY KEY(participant,story))",
    "CREATE TABLE readings (participant TEXT REFERENCES participants(id), "
    "story TEXT REFERENCES stories(id), PRIMARY KEY(participant,story))",
    "CREATE TABLE assignments (id TEXT PRIMARY KEY, participant TEXT REFERENCES "
    "participants(id), position INTEGER NOT NULL, criterion TEXT NOT NULL, "
    "left_id TEXT REFERENCES stories(id), right_id TEXT REFERENCES stories(id), "
    "issued_at TEXT NOT NULL, void INTEGER NOT NULL DEFAULT 0)",
    "CREATE TABLE votes (assignment TEXT PRIMARY KEY REFERENCES assignments(id), choice TEXT "
    "CHECK(choice IN ('A','B','abstain')), seconds REAL, created_at TEXT NOT NULL)",
)
_PRIVATE_KEYS = (
    "path",
    "directory",
    "run_dir",
    "output_root",
    "telegram",
    "chat_id",
    "user_id",
    "username",
    "external_id",
    "api_key",
    "access_token",
    "bot_token",
    "password",
)


def now() -> str:
    """Return a timezone-aware audit timestamp."""
    return datetime.now(UTC).isoformat()


def identifier(prefix: str) -> str:
    """Create an opaque identifier safe for short callback payloads."""
    return prefix + uuid.uuid4().hex[:16]


def portable_provenance(value):
    """Remove administrative identifiers and host paths from nested run artifacts."""
    if isinstance(value, dict):
        return {
            key: portable_provenance(item)
            for key, item in value.items()
            if not any(term in key.lower() for term in _PRIVATE_KEYS)
        }
    if isinstance(value, list):
        return [portable_provenance(item) for item in value]
    return value


def read_candidate(directory: str | Path) -> dict:
    """Validate a completed prose run without importing its generator's schema."""
    directory = Path(directory).resolve()
    story = directory / "story.md"
    text = story.read_text(encoding="utf-8") if story.is_file() else ""
    metadata = load_json_object(directory / "metadata.json")
    options = load_json_object(directory / "generation_options.json")
    request = load_json_object(directory / "request.json")
    fmt = options.get("story_format", metadata.get("story_format"))
    if metadata.get("status") != "completed" or fmt not in PROSE_FORMATS or not text.strip():
        raise ValueError(f"{directory.name}: el estudio solo admite historias completas en prosa.")
    provenance = {
        "metadata": metadata,
        "options": options,
        "version": load_json_object(directory / "generator_version.json"),
        "request": request,
    }
    return {
        "run_path": str(directory),
        "text": text,
        "text_hash": digest(text),
        "provenance": provenance,
        "family": digest(request.get("original_prompt", text)),
    }


def coverage(story_ids: list[str], assignments: list[dict], votes: list[dict]) -> dict:
    """Report issued and decided connectivity without treating abstention as a tie."""
    result = {}
    for criterion in CRITERIA:
        issued = [q for q in assignments if q["criterion"] == criterion and not q["void"]]
        observed = [v for v in votes if v["criterion"] == criterion]
        decided = [v for v in observed if v["choice"] != "abstain"]
        counts = Counter(s for v in decided for s in (v["left"], v["right"]))
        result[criterion] = {
            "issued": len(issued),
            "votes": len(observed),
            "abstentions": len(observed) - len(decided),
            "comparisons": {s: counts[s] for s in story_ids},
            "components": components(story_ids, [(v["left"], v["right"]) for v in decided]),
        }
    return result


class StudyRepository:
    """Keep one study, its frozen pool, readers, questions and votes in SQLite."""

    def __init__(self, path: str | Path, study_id: str | None = None) -> None:
        """Open a study, creating its schema and collection phase on first use."""
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.transaction() as db:
            version = db.execute("PRAGMA user_version").fetchone()[0]
            if version not in (0, SCHEMA_VERSION):
                raise ValueError(
                    f"{self.path} es de un estudio anterior (esquema {version}); "
                    "usa una base nueva."
                )
            if version == 0:
                for statement in _SCHEMA:
                    db.execute(statement)
                db.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
            if db.execute("SELECT 1 FROM study").fetchone() is None:
                db.execute(
                    "INSERT INTO study(id,state,seed,created_at) VALUES (?,?,?,?)",
                    (study_id or self.path.parent.name or "estudio", "collection", 42, now()),
                )

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

    @staticmethod
    def _require(db, *states: str) -> dict:
        """Enforce the phase inside the same transaction as a mutation."""
        row = dict(db.execute("SELECT * FROM study").fetchone())
        if row["state"] not in states:
            messages = {
                "collection": "La recogida de historias ya terminó.",
                "evaluation": "La votación no está abierta.",
            }
            raise ValueError(messages.get(states[0], "La operación no está disponible ahora."))
        return row

    def info(self) -> dict:
        """Read the phase, seed and frozen snapshot."""
        with self.transaction() as db:
            result = dict(db.execute("SELECT * FROM study").fetchone())
        result["snapshot"] = json.loads(result["snapshot"]) if result["snapshot"] else None
        return result

    def participant(self, external_id: str) -> str:
        """Register a reader or creator by external id and return their pseudonym."""
        with self.transaction() as db:
            return self._participant(db, external_id)

    @staticmethod
    def _participant(db, external_id: str) -> str:
        """Find or insert one pseudonymous participant inside a transaction."""
        row = db.execute(
            "SELECT id FROM participants WHERE external_id=?", (str(external_id),)
        ).fetchone()
        if row:
            return row["id"]
        pid = identifier("p")
        db.execute("INSERT INTO participants(id,external_id) VALUES (?,?)", (pid, str(external_id)))
        return pid

    def mark_author(self, external_id: str) -> str:
        """Flag the researcher so agreement can be reported with and without them."""
        with self.transaction() as db:
            pid = self._participant(db, external_id)
            db.execute("UPDATE participants SET is_author=1 WHERE id=?", (pid,))
        return pid

    def add_story(
        self, directory: str | Path, *, owner: str | None = None, family: str | None = None
    ) -> str:
        """Enroll one completed prose run during collection, idempotently by run path."""
        candidate = read_candidate(directory)
        with self.transaction() as db:
            self._require(db, "collection")
            existing = db.execute(
                "SELECT id,text_hash FROM stories WHERE run_path=?", (candidate["run_path"],)
            ).fetchone()
            if existing:
                if existing["text_hash"] != candidate["text_hash"]:
                    raise ValueError("Un relato inscrito no puede cambiar de texto.")
                return existing["id"]
            if db.execute(
                "SELECT 1 FROM stories WHERE text_hash=?", (candidate["text_hash"],)
            ).fetchone():
                raise ValueError("Este texto ya está inscrito en el estudio.")
            sid = identifier("s")
            db.execute(
                "INSERT INTO stories(id,run_path,text,text_hash,provenance,owner,family) "
                "VALUES (?,?,?,?,?,?,?)",
                (
                    sid,
                    candidate["run_path"],
                    candidate["text"],
                    candidate["text_hash"],
                    json.dumps(candidate["provenance"], ensure_ascii=False),
                    owner,
                    family or candidate["family"],
                ),
            )
        return sid

    def exclude(self, story: str, excluded: bool = True) -> None:
        """Keep an enrolled story out of (or back in) the pool before voting opens."""
        with self.transaction() as db:
            self._require(db, "collection")
            if not db.execute(
                "UPDATE stories SET excluded=? WHERE id=?", (int(excluded), story)
            ).rowcount:
                raise ValueError("No existe esa historia en el estudio.")

    @staticmethod
    def _pool(db) -> list[dict]:
        """Return the stories that take part in the comparisons."""
        rows = db.execute("SELECT * FROM stories WHERE excluded=0 ORDER BY id").fetchall()
        result = [dict(row) for row in rows]
        for row in result:
            row["provenance"] = json.loads(row["provenance"])
        return result

    def open(self) -> dict:
        """Freeze the pool with its catalog and open the vote."""
        with self.transaction() as db:
            info = self._require(db, "collection")
            pool = self._pool(db)
            if len(pool) < MIN_POOL:
                raise ValueError(f"Hacen falta al menos {MIN_POOL} historias para votar.")
            for story in pool:
                if read_candidate(story["run_path"])["text_hash"] != story["text_hash"]:
                    raise ValueError(f"El texto de {story['id']} cambió desde su inscripción.")
            snapshot = {
                "catalog": catalog_snapshot(),
                "guidance": guidance(),
                "seed": info["seed"],
                "stories": [
                    {k: s[k] for k in ("id", "text_hash", "provenance", "owner", "family")}
                    for s in pool
                ],
            }
            snapshot["sha256"] = digest(snapshot)
            db.execute(
                "UPDATE study SET state='evaluation', snapshot=?, opened_at=?",
                (json.dumps(snapshot, ensure_ascii=False), now()),
            )
        return snapshot

    def close(self) -> None:
        """End the vote; recorded answers stay untouched."""
        with self.transaction() as db:
            self._require(db, "evaluation")
            db.execute("UPDATE study SET state='closed', closed_at=?", (now(),))

    @staticmethod
    def _pending(db, participant: str):
        """Find the reader's open question, if any."""
        return db.execute(
            "SELECT a.* FROM assignments a LEFT JOIN votes v ON v.assignment=a.id "
            "WHERE a.participant=? AND a.void=0 AND v.assignment IS NULL",
            (participant,),
        ).fetchone()

    def next_question(self, participant: str) -> dict | None:
        """Return the reader's open question, or assign a new one, or None when done."""
        with self.transaction() as db:
            info = self._require(db, "evaluation")
            row = self._pending(db, participant)
            if row is None:
                row = self._assign(db, participant, info["seed"])
            if row is None:
                return None
            result = {
                "id": row["id"],
                "criterion": row["criterion"],
                "question": questions()[row["criterion"]],
                "guidance": guidance()[row["criterion"]],
                "position": row["position"],
                "total": QUESTIONS_PER_READER,
            }
            for side, key in (("left", "left_id"), ("right", "right_id")):
                story = db.execute(
                    "SELECT id,text,run_path FROM stories WHERE id=?", (row[key],)
                ).fetchone()
                read = db.execute(
                    "SELECT 1 FROM readings WHERE participant=? AND story=?",
                    (participant, story["id"]),
                ).fetchone()
                result[side] = {**dict(story), "read": bool(read)}
            return result

    def _assign(self, db, participant: str, seed: int):
        """Pick the next pair: fewest unread stories, least compared pair, rarest stories."""
        issued = db.execute("SELECT * FROM assignments WHERE void=0").fetchall()
        mine = [q for q in issued if q["participant"] == participant]
        if len(mine) >= QUESTIONS_PER_READER:
            return None
        criterion = CRITERIA[len(mine) % len(CRITERIA)]
        hidden = {
            r[0]
            for r in db.execute(
                "SELECT story FROM known WHERE participant=? UNION "
                "SELECT id FROM stories WHERE owner=?",
                (participant, participant),
            )
        }
        eligible = [s["id"] for s in self._pool(db) if s["id"] not in hidden]
        asked = {
            frozenset((q["left_id"], q["right_id"])) for q in mine if q["criterion"] == criterion
        }
        read = {
            r[0]
            for r in db.execute("SELECT story FROM readings WHERE participant=?", (participant,))
        }
        pairs = Counter(
            frozenset((q["left_id"], q["right_id"])) for q in issued if q["criterion"] == criterion
        )
        appearances = Counter(s for q in issued for s in (q["left_id"], q["right_id"]))
        lefts = Counter(q["left_id"] for q in issued)
        rng = random.Random(f"{seed}:{participant}:{len(mine)}")
        candidates = [
            (
                (a not in read) + (b not in read),
                pairs[frozenset((a, b))],
                appearances[a] + appearances[b],
                rng.random(),
                a,
                b,
            )
            for a, b in combinations(eligible, 2)
            if frozenset((a, b)) not in asked
        ]
        if not candidates:
            return None
        *_, a, b = min(candidates)
        # Balance which story is shown as A; break ties at random.
        if lefts[a] > lefts[b] or (lefts[a] == lefts[b] and rng.random() < 0.5):
            a, b = b, a
        qid = identifier("q")
        db.execute(
            "INSERT INTO assignments(id,participant,position,criterion,left_id,right_id,"
            "issued_at) VALUES (?,?,?,?,?,?,?)",
            (qid, participant, len(mine) + 1, criterion, a, b, now()),
        )
        return db.execute("SELECT * FROM assignments WHERE id=?", (qid,)).fetchone()

    def _active(self, db, participant: str, question: str, story: str | None = None):
        """Return the reader's open question, rejecting stale buttons."""
        row = self._pending(db, participant)
        if (
            row is None
            or row["id"] != question
            or (story is not None and story not in (row["left_id"], row["right_id"]))
        ):
            raise ValueError("Esta pregunta ya no está activa.")
        return row

    def mark_read(self, participant: str, question: str, story: str) -> None:
        """Record that the reader finished one story of the open question."""
        with self.transaction() as db:
            self._require(db, "evaluation")
            self._active(db, participant, question, story)
            db.execute("INSERT OR IGNORE INTO readings VALUES (?,?)", (participant, story))

    def recognize(self, participant: str, question: str, story: str) -> None:
        """Hide a story the reader already knew and drop the question that showed it."""
        with self.transaction() as db:
            self._require(db, "evaluation")
            self._active(db, participant, question, story)
            db.execute("INSERT OR IGNORE INTO known VALUES (?,?)", (participant, story))
            db.execute("UPDATE assignments SET void=1 WHERE id=?", (question,))

    def vote(self, participant: str, question: str, choice: str) -> bool:
        """Save A, B or abstain once both stories are read; False if already answered."""
        if choice not in {"A", "B", "abstain"}:
            raise ValueError("Respuesta desconocida.")
        with self.transaction() as db:
            self._require(db, "evaluation")
            if db.execute(
                "SELECT 1 FROM votes v JOIN assignments a ON a.id=v.assignment "
                "WHERE v.assignment=? AND a.participant=?",
                (question, participant),
            ).fetchone():
                return False
            row = self._active(db, participant, question)
            reads = db.execute(
                "SELECT COUNT(*) FROM readings WHERE participant=? AND story IN (?,?)",
                (participant, row["left_id"], row["right_id"]),
            ).fetchone()[0]
            if reads != 2:
                raise ValueError("Confirma primero la lectura de ambas historias.")
            seconds = (datetime.now(UTC) - datetime.fromisoformat(row["issued_at"])).total_seconds()
            db.execute(
                "INSERT INTO votes VALUES (?,?,?,?)", (question, choice, max(0, seconds), now())
            )
        return True

    def status(self) -> dict:
        """Summarize the phase, the pool and the answers for the operator."""
        data = self.export()
        excluded = data.pop("excluded")
        return {
            "study": data["study"]["id"],
            "state": data["study"]["state"],
            "stories": [
                {
                    "id": s["id"],
                    "format": s["provenance"]["options"].get("story_format")
                    or s["provenance"]["metadata"].get("story_format"),
                    "owner": s["owner"],
                }
                for s in data["stories"]
            ],
            "excluded": excluded,
            "participants": len(data["participants"]),
            "votes": len(data["votes"]),
            "coverage": {
                c: {k: v[k] for k in ("issued", "votes", "abstentions")}
                for c, v in data["coverage"].items()
            },
        }

    def export(self) -> dict:
        """Export pseudonymous research data without external account ids or local paths."""
        with self.transaction() as db:
            stories = self._pool(db)
            excluded = [r[0] for r in db.execute("SELECT id FROM stories WHERE excluded=1")]
            for story in stories:
                story.pop("run_path")
                story.pop("excluded")
                story["provenance"] = portable_provenance(story["provenance"])
            participants = [
                dict(r) for r in db.execute("SELECT id,is_author FROM participants ORDER BY id")
            ]
            assignments = [
                dict(r)
                for r in db.execute(
                    "SELECT id,participant,position,criterion,left_id AS 'left',"
                    "right_id AS 'right',issued_at,void FROM assignments "
                    "ORDER BY participant,position,issued_at"
                )
            ]
            votes = [
                dict(r)
                for r in db.execute(
                    "SELECT a.id,a.participant,a.criterion,a.left_id AS 'left',"
                    "a.right_id AS 'right',v.choice,v.seconds,v.created_at "
                    "FROM votes v JOIN assignments a ON a.id=v.assignment ORDER BY v.created_at"
                )
            ]
            readings = [dict(r) for r in db.execute("SELECT * FROM readings")]
            known = [dict(r) for r in db.execute("SELECT * FROM known")]
            info = dict(db.execute("SELECT * FROM study").fetchone())
        info["snapshot"] = json.loads(info["snapshot"]) if info["snapshot"] else None
        return {
            "schema_version": SCHEMA_VERSION,
            "study": portable_provenance(info),
            "stories": stories,
            "excluded": excluded,
            "participants": participants,
            "assignments": assignments,
            "votes": votes,
            "readings": readings,
            "known": known,
            "coverage": coverage([s["id"] for s in stories], assignments, votes),
        }
