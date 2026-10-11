"""Reconstruct an offline analysis database from a verified pseudonymous export."""

from __future__ import annotations

import json


def restore_analysis_database(data: dict, destination) -> None:
    """Restore stable research identities while replacing all server filesystem paths."""
    from .study import StudyRepository

    repository = StudyRepository(destination / "study.sqlite3")
    info = data["study"]
    repository.create(
        info["id"],
        required_version=info["required_version"],
        seed=info["seed"],
        mode=info.get("mode", "fixed"),
    )
    with repository.transaction() as db:
        db.execute(
            "UPDATE study SET state=?,snapshot=?,revision=?,created_at=?",
            (
                info["state"],
                json.dumps(info["snapshot"], ensure_ascii=False) if info["snapshot"] else None,
                info.get("revision", 0),
                info["created_at"],
            ),
        )
        for reader in data["participants"]:
            db.execute(
                "INSERT INTO participants(id,profile,is_author) VALUES (?,?,?)",
                (reader["id"], reader["profile"], reader["is_author"]),
            )
        for story in data["stories"]:
            directory = destination / "stories" / story["id"]
            db.execute(
                "INSERT INTO stories(id,run_path,text,text_hash,provenance,"
                "owner,curated,family,active) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    story["id"],
                    str(directory.resolve()),
                    story["text"],
                    story["text_hash"],
                    json.dumps(story["provenance"], ensure_ascii=False),
                    story["owner"],
                    story["curated"],
                    story["family"],
                    story.get("active", 1),
                ),
            )
        for question in data["assignments"]:
            db.execute(
                "INSERT INTO assignments VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    question["id"],
                    question["participant"],
                    question["session"],
                    question["position"],
                    question["criterion"],
                    question["left"],
                    question["right"],
                    question.get("issued_at"),
                    question["void"],
                ),
            )
        for vote in data["votes"]:
            db.execute(
                "INSERT INTO votes VALUES (?,?,?,?)",
                (vote["id"], vote["choice"], vote["seconds"], vote["created_at"]),
            )
        for reading in data.get("readings", []):
            db.execute(
                "INSERT INTO readings VALUES (?,?)", (reading["participant"], reading["story"])
            )
        for exposure in data.get("exposures", []):
            db.execute(
                "INSERT INTO exposures VALUES (?,?)",
                (exposure["participant"], exposure["text_hash"]),
            )
        for contribution in data.get("first_contributions", []):
            db.execute(
                "INSERT INTO first_contributions VALUES (?,?)",
                (contribution["participant"], contribution["story"]),
            )
        for entry in data.get("pack", []):
            db.execute(
                "INSERT INTO pack VALUES (?,?,?)", (entry["story"], entry["slot"], entry["format"])
            )
        for request in data.get("author_requests", []):
            db.execute(
                "INSERT INTO author_requests(slot,prompt,format,story) VALUES (?,?,?,?)",
                (request["slot"], request["prompt"], request["format"], request["story"]),
            )
        for session in data.get("sessions", []):
            db.execute(
                "INSERT INTO sessions VALUES (?,?,?,?,?)",
                (
                    session["participant"],
                    session["number"],
                    session["revision"],
                    session["seed"],
                    session["pool"],
                ),
            )
