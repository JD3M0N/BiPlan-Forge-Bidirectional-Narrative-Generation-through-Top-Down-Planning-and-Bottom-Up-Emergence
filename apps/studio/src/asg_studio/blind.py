"""Blind reading sessions: pairs of stories read as X and Y, and the vote given to each pair.

A session is a manifest, Evaluations/estudio/lecturas/<name>.json, that lists pairs of
"collection/run" references already in the order the reader will see them. Which arm of the
experiment sits behind X or Y is never in the manifest nor in any response; the key is kept
elsewhere and the votes are unblinded outside this tool. Votes go to <name>.votos.json beside the
manifest, never under Stories/.
"""

from __future__ import annotations

import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .library import Library

_SESSION_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
WINNERS = ("x", "y", "ninguno")


class SessionNotFound(LookupError):
    """Raised when a reading session or one of its pairs does not exist."""


class BlindStudy:
    """Read the manifests of one folder and keep the votes beside them."""

    def __init__(self, folder: Path, library: Library) -> None:
        """Remember where the sessions live and which library resolves their runs."""
        self.folder = Path(folder)
        self.library = library

    def sessions(self) -> list[dict[str, Any]]:
        """List the sessions with how many of their pairs already have a vote."""
        if not self.folder.is_dir():
            return []
        found = []
        for path in sorted(self.folder.glob("*.json")):
            name = path.stem
            if not _SESSION_NAME.match(name) or name.endswith("votos"):
                continue
            try:
                pairs = self._pairs(name)
            except SessionNotFound:
                continue
            found.append({"name": name, "total": len(pairs), "voted": len(self._votes(name))})
        return found

    def pair(self, name: str, number: int) -> dict[str, Any]:
        """Return both stories of one pair, with no run id, title or axis, and its vote."""
        pairs = self._pairs(name)
        if not 1 <= number <= len(pairs):
            raise SessionNotFound(f"{name}/{number}")
        entry = pairs[number - 1]
        vote = self._votes(name).get(str(number))
        return {
            "number": number,
            "total": len(pairs),
            "x": self._story(entry["x"]),
            "y": self._story(entry["y"]),
            "vote": vote["ganador"] if vote else None,
        }

    def vote(self, name: str, number: int, winner: str) -> dict[str, Any]:
        """Record the winner of one pair, replacing an earlier vote, and return the progress."""
        pairs = self._pairs(name)
        if not 1 <= number <= len(pairs):
            raise SessionNotFound(f"{name}/{number}")
        votes = self._votes(name)
        stamp = datetime.now(UTC).isoformat(timespec="seconds")
        votes[str(number)] = {"ganador": winner, "fecha": stamp}
        self._write(name, votes)
        return {"voted": len(votes), "total": len(pairs)}

    def tally(self, name: str) -> dict[str, int]:
        """Count the votes of a session by position: X, Y or no difference."""
        counts = dict.fromkeys(WINNERS, 0)
        for vote in self._votes(name).values():
            counts[vote["ganador"]] += 1
        return counts

    # -- storage -------------------------------------------------------------------------

    def _pairs(self, name: str) -> list[dict[str, str]]:
        """Read the pairs of a manifest, refusing a name that is not one."""
        if not _SESSION_NAME.match(name or "") or name.endswith("votos"):
            raise SessionNotFound(name)
        try:
            document = json.loads((self.folder / f"{name}.json").read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            raise SessionNotFound(name) from error
        pairs = document.get("pares") if isinstance(document, dict) else None
        if not isinstance(pairs, list) or not all(
            isinstance(item, dict)
            and isinstance(item.get("x"), str)
            and isinstance(item.get("y"), str)
            for item in pairs
        ):
            raise SessionNotFound(name)
        return pairs

    def _votes(self, name: str) -> dict[str, dict[str, str]]:
        """Read the votes saved so far, or none when the file is missing or unreadable."""
        try:
            document = json.loads(self._votes_path(name).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        votes = document.get("votos") if isinstance(document, dict) else None
        if not isinstance(votes, dict):
            return {}
        return {
            str(key): value
            for key, value in votes.items()
            if isinstance(value, dict) and value.get("ganador") in WINNERS
        }

    def _write(self, name: str, votes: dict[str, dict[str, str]]) -> None:
        """Save the votes by writing a temporary file and replacing the old one."""
        path = self._votes_path(name)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        document = {"sesion": name, "votos": votes}
        temporary.write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temporary, path)

    def _votes_path(self, name: str) -> Path:
        """Return where the votes of a session are kept."""
        return self.folder / f"{name}.votos.json"

    def _story(self, reference: str) -> dict[str, Any]:
        """Return the chapters of one story, without the title that could give its arm away."""
        return {"chapters": self.library.blind_story(reference)["chapters"]}
