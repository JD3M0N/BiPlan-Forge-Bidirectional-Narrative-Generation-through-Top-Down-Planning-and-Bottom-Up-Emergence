"""Fixed ten-story pack: six participant contributions plus four researcher stories."""

from __future__ import annotations

import json
from pathlib import Path

from .catalog import catalog_snapshot, digest, guidance

PACK_FORMATS = ("narrative", "simulated")
PACK_QUOTAS = {"participant": 3, "author": 2}
PACK_SESSION_SIZE = 5
AUTHOR_ATTEMPTS = 3


def migrate_pack(db) -> None:
    """Add pack membership, researcher requests and blind format assignment."""
    if "format" not in {row[1] for row in db.execute("PRAGMA table_info(contributions)")}:
        db.execute("ALTER TABLE contributions ADD COLUMN format TEXT")
    db.execute(
        "CREATE TABLE IF NOT EXISTS pack (story TEXT PRIMARY KEY REFERENCES stories(id), "
        "slot TEXT NOT NULL, format TEXT NOT NULL)"
    )
    db.execute(
        "CREATE TABLE IF NOT EXISTS author_requests (slot INTEGER PRIMARY KEY, "
        "prompt TEXT NOT NULL, format TEXT NOT NULL, job_id TEXT, "
        "story TEXT REFERENCES stories(id), attempts INTEGER NOT NULL DEFAULT 0)"
    )


def read_author_requests(path: str | Path) -> list[dict]:
    """Validate the researcher's prompts: two per pack format, non-empty."""
    entries = json.loads(Path(path).read_text(encoding="utf-8"))
    requests = [
        {"prompt": str(entry.get("prompt", "")).strip(), "format": entry.get("format")}
        for entry in entries
    ]
    formats = [entry["format"] for entry in requests]
    if any(not entry["prompt"] for entry in requests) or sorted(formats) != sorted(
        PACK_FORMATS * PACK_QUOTAS["author"]
    ):
        raise ValueError("Se requieren cuatro prompts del autor: dos narrative y dos simulated.")
    return requests


def story_format(candidate: dict) -> str | None:
    """Read the prose format a run was generated with."""
    provenance = candidate["provenance"]
    return provenance["options"].get("story_format", provenance["metadata"].get("story_format"))


class PackStudy:
    """Fill a frozen pack from the first balanced contributions and open voting."""

    def load_author_requests(self, path: str | Path) -> int:
        """Store the researcher's four requests once, before evaluation."""
        requests = read_author_requests(path)
        with self.transaction() as db:
            info = self._require(db, "preparation", "collection")
            if info["mode"] != "pack":
                raise ValueError("Los prompts del autor solo existen en un estudio pack.")
            if db.execute("SELECT 1 FROM author_requests").fetchone():
                raise ValueError("Los prompts del autor ya están cargados.")
            for slot, entry in enumerate(requests, 1):
                db.execute(
                    "INSERT INTO author_requests(slot,prompt,format) VALUES (?,?,?)",
                    (slot, entry["prompt"], entry["format"]),
                )
        return len(requests)

    def pending_author_requests(self) -> list[dict]:
        """List researcher requests without a story that may still be attempted."""
        with self.transaction() as db:
            rows = db.execute(
                "SELECT slot,prompt,format,job_id,attempts FROM author_requests "
                "WHERE story IS NULL AND attempts<? ORDER BY slot",
                (AUTHOR_ATTEMPTS,),
            ).fetchall()
        return [dict(row) for row in rows]

    def bind_author_job(self, slot: int, job_id: str) -> None:
        """Bind one researcher request to a durable generation job."""
        with self.transaction() as db:
            db.execute(
                "UPDATE author_requests SET job_id=?,attempts=attempts+1 "
                "WHERE slot=? AND story IS NULL",
                (job_id, slot),
            )

    def complete_author_generation(self, job_id: str, directory: Path) -> bool:
        """Enroll a finished researcher job as a curated story of the pack."""
        with self.transaction() as db:
            row = db.execute(
                "SELECT slot FROM author_requests WHERE job_id=? AND story IS NULL", (job_id,)
            ).fetchone()
        if row is None:
            return False
        sid = self.add_story(directory, curated=True)
        with self.transaction() as db:
            db.execute("UPDATE author_requests SET story=? WHERE slot=?", (sid, row["slot"]))
        return True

    def assign_format(self, participant: str) -> str:
        """Give a contribution the pack format with fewer stories, keeping it on retries."""
        with self.transaction() as db:
            row = db.execute(
                "SELECT format FROM contributions WHERE participant=?", (participant,)
            ).fetchone()
            if row is None:
                raise ValueError("Primero reserva la aportación.")
            if row["format"]:
                return row["format"]
            counts = {fmt: 0 for fmt in PACK_FORMATS}
            for (fmt,) in db.execute("SELECT format FROM pack WHERE slot='participant'"):
                counts[fmt] += 1
            for (fmt,) in db.execute(
                "SELECT format FROM contributions WHERE pending=1 AND job_id IS NOT NULL "
                "AND format IS NOT NULL AND participant<>?",
                (participant,),
            ):
                counts[fmt] += 1
            chosen = min(PACK_FORMATS, key=lambda fmt: counts[fmt])
            db.execute(
                "UPDATE contributions SET format=? WHERE participant=?", (chosen, participant)
            )
        return chosen

    def assigned_format(self, external_id: str, job_id: str) -> str | None:
        """Return the hidden format of a job reserved as a pack contribution."""
        with self.transaction() as db:
            row = db.execute(
                "SELECT c.format FROM contributions c JOIN participants p ON p.id=c.participant "
                "WHERE p.external_id=? AND c.job_id=?",
                (str(external_id), job_id),
            ).fetchone()
        return row[0] if row else None

    def in_pack(self, external_id: str) -> bool:
        """Tell whether a participant's contribution took one of the pack slots."""
        with self.transaction() as db:
            row = db.execute(
                "SELECT 1 FROM pack JOIN stories s ON s.id=pack.story "
                "JOIN participants p ON p.id=s.owner WHERE p.external_id=?",
                (str(external_id),),
            ).fetchone()
        return row is not None

    def pack_complete(self) -> bool:
        """Tell whether every pack slot is filled."""
        with self.transaction() as db:
            return self._pack_full(db)

    @staticmethod
    def _pack_full(db) -> bool:
        """Compare filled slots with the per-format quotas."""
        counts = {
            (row[0], row[1]): row[2]
            for row in db.execute("SELECT slot,format,COUNT(*) FROM pack GROUP BY slot,format")
        }
        return all(
            counts.get((slot, fmt), 0) >= quota
            for slot, quota in PACK_QUOTAS.items()
            for fmt in PACK_FORMATS
        )

    def _pack_enrolled(self, db, sid: str, owner, curated: bool, fmt) -> None:
        """Place a new story in a free pack slot and open voting when the pack is full."""
        info = dict(db.execute("SELECT * FROM study").fetchone())
        if info["mode"] != "pack" or info["state"] != "collection" or fmt not in PACK_FORMATS:
            return
        slot = "author" if curated else "participant" if owner else None
        if slot is None:
            return
        filled = db.execute(
            "SELECT COUNT(*) FROM pack WHERE slot=? AND format=?", (slot, fmt)
        ).fetchone()[0]
        if filled >= PACK_QUOTAS[slot]:
            return
        db.execute("INSERT INTO pack VALUES (?,?,?)", (sid, slot, fmt))
        if not self._pack_full(db):
            return
        snapshot = {
            "catalog": catalog_snapshot(),
            "guidance": guidance(),
            "seed": info["seed"],
            "mode": "pack",
            "pack": [
                dict(row) for row in db.execute("SELECT story,slot,format FROM pack ORDER BY story")
            ],
        }
        snapshot["sha256"] = digest(snapshot)
        db.execute(
            "UPDATE study SET state='evaluation',snapshot=?",
            (json.dumps(snapshot, ensure_ascii=False),),
        )
