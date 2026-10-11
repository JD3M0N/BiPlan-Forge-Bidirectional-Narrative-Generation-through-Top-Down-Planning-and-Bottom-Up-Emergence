"""Explicit publication permission and a durable outbox for approved story texts."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta


class PublicationStore:
    """Keep publication permission separate from participation and research exports."""

    def publication_consent(self, participant: str, allowed: bool | None = None):
        """Read or record permission to publish the participant's story text."""
        with self.transaction() as db:
            if allowed is not None:
                db.execute(
                    "INSERT INTO publication_consent VALUES (?,?) ON CONFLICT(participant) "
                    "DO UPDATE SET allowed=excluded.allowed",
                    (participant, int(allowed)),
                )
                if not allowed:
                    db.execute(
                        "DELETE FROM publications WHERE synced_at IS NULL AND story IN "
                        "(SELECT id FROM stories WHERE owner=?)",
                        (participant,),
                    )
            row = db.execute(
                "SELECT allowed FROM publication_consent WHERE participant=?", (participant,)
            ).fetchone()
        return bool(row[0]) if row else None

    def publication_candidates(self) -> list[dict]:
        """List authorized stories that still need investigator review."""
        with self.transaction() as db:
            return [
                dict(row)
                for row in db.execute(
                    "SELECT s.id,s.text,s.text_hash FROM stories s LEFT JOIN publication_consent c "
                    "ON c.participant=s.owner WHERE s.active=1 AND "
                    "((s.curated=1 AND s.owner IS NULL) OR c.allowed=1) AND NOT EXISTS "
                    "(SELECT 1 FROM publications p WHERE p.story=s.id) ORDER BY s.id"
                )
            ]

    def approve_publication(self, story: str, text_hash: str) -> None:
        """Approve exactly the immutable text the investigator reviewed."""
        with self.transaction() as db:
            row = db.execute(
                "SELECT s.* FROM stories s LEFT JOIN publication_consent c "
                "ON c.participant=s.owner WHERE s.id=? AND s.active=1 AND "
                "((s.curated=1 AND s.owner IS NULL) OR c.allowed=1)",
                (story,),
            ).fetchone()
            if not row or row["text_hash"] != text_hash:
                raise ValueError("El texto no coincide o no tiene autorización para publicarse.")
            db.execute(
                "INSERT OR IGNORE INTO publications(story,approved_at) VALUES (?,?)",
                (story, datetime.now(UTC).isoformat()),
            )

    def publication_batch(self) -> list[dict]:
        """Read approved public payloads, never metadata or reader identifiers."""
        with self.transaction() as db:
            return [
                dict(row)
                for row in db.execute(
                    "SELECT s.id,s.text,s.text_hash,p.synced_at,p.next_attempt,p.attempts "
                    "FROM publications p JOIN stories s ON s.id=p.story "
                    "LEFT JOIN publication_consent c ON c.participant=s.owner "
                    "WHERE p.synced_at IS NOT NULL OR (s.curated=1 AND s.owner IS NULL) "
                    "OR c.allowed=1 ORDER BY s.id"
                )
            ]

    def publication_result(self, story: str, *, success: bool, error: str = "") -> None:
        """Persist bounded backoff after a publication attempt."""
        moment = datetime.now(UTC)
        with self.transaction() as db:
            row = db.execute("SELECT attempts FROM publications WHERE story=?", (story,)).fetchone()
            if not row:
                return
            delay = min(3600, 60 * 2 ** min(row[0], 6))
            db.execute(
                "UPDATE publications SET synced_at=?,attempts=attempts+1,next_attempt=?,error=? "
                "WHERE story=?",
                (
                    moment.isoformat() if success else None,
                    None if success else (moment + timedelta(seconds=delay)).isoformat(),
                    error[:200],
                    story,
                ),
            )
