"""Persistent per-provider quota ledger shared by every process that generates stories.

A provider chain asks the ledger before each call whether a slot (one provider and one model)
still has allowance in its current window, and tells it what each call spent. The ledger also
remembers a slot a provider declared exhausted, until that slot's window resets, so a spent
quota is never rediscovered by spending another request on it.

The caps are configuration, never constants: free tiers change without notice. A slot without
caps is only ever skipped after its provider says so.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from contextlib import closing
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal

Window = Literal["pacific_day", "utc_day", "utc_month"]
Clock = Callable[[], datetime]


@dataclass(frozen=True)
class QuotaSlot:
    """Name one provider and model, the window its allowance resets in, and its caps."""

    provider: str
    model: str
    window: Window = "utc_day"
    max_requests: int = 0
    max_tokens: int = 0

    @property
    def key(self) -> str:
        """Return the ledger key and the name surfaces show for this slot."""
        return f"{self.provider}:{self.model}"


def _nth_sunday(year: int, month: int, n: int) -> int:
    """Return the day of the month of its n-th Sunday."""
    first = datetime(year, month, 1).weekday()
    return 1 + (6 - first) % 7 + 7 * (n - 1)


def _pacific_offset(moment: datetime) -> timedelta:
    """Return the US Pacific UTC offset at a moment, without needing the tz database.

    Windows ships no IANA database and tzdata is not a dependency; the US rule (second Sunday
    of March to first Sunday of November, at 02:00 local) is all Gemini's reset needs.
    """
    year = moment.year
    dst_start = datetime(year, 3, _nth_sunday(year, 3, 2), 10, tzinfo=UTC)
    dst_end = datetime(year, 11, _nth_sunday(year, 11, 1), 9, tzinfo=UTC)
    return timedelta(hours=-7) if dst_start <= moment < dst_end else timedelta(hours=-8)


def window_bounds(window: Window, moment: datetime) -> tuple[str, datetime]:
    """Return the label of the window a moment falls in and the instant it resets."""
    if window == "pacific_day":
        local = moment + _pacific_offset(moment)
        # Next local midnight, written as a UTC-labelled wall clock, then shifted by the offset
        # in force at that midnight, which differs from today's on the two DST days.
        midnight = datetime(local.year, local.month, local.day, tzinfo=UTC) + timedelta(days=1)
        reset = midnight - _pacific_offset(midnight - _pacific_offset(moment))
        return f"{local:%Y-%m-%d}", reset
    if window == "utc_month":
        start = datetime(moment.year, moment.month, 1, tzinfo=UTC)
        reset = (start + timedelta(days=32)).replace(day=1)
        return f"{moment:%Y-%m}", reset
    start = datetime(moment.year, moment.month, moment.day, tzinfo=UTC)
    return f"{moment:%Y-%m-%d}", start + timedelta(days=1)


class QuotaLedger:
    """Count requests and tokens per slot and window in SQLite, safe across processes."""

    def __init__(self, path: Path, *, clock: Clock | None = None) -> None:
        """Open, or create, the ledger at path."""
        self.path = path
        self._clock = clock or (lambda: datetime.now(UTC))
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS usage (slot TEXT, window TEXT, requests INTEGER, "
                "tokens INTEGER, PRIMARY KEY (slot, window))"
            )
            db.execute("CREATE TABLE IF NOT EXISTS exhausted (slot TEXT PRIMARY KEY, until TEXT)")

    def _connect(self) -> closing[sqlite3.Connection]:
        """Open one short-lived connection; SQLite serializes writers between processes."""
        return closing(sqlite3.connect(self.path, timeout=30, isolation_level=None))

    def usage(self, slot: QuotaSlot) -> tuple[int, int]:
        """Return the requests and tokens a slot has spent in its current window."""
        label, _ = window_bounds(slot.window, self._clock())
        with self._connect() as db:
            row = db.execute(
                "SELECT requests, tokens FROM usage WHERE slot = ? AND window = ?",
                (slot.key, label),
            ).fetchone()
        return (int(row[0]), int(row[1])) if row else (0, 0)

    def exhausted_until(self, slot: QuotaSlot) -> datetime | None:
        """Return when a slot a provider declared exhausted becomes usable, if it is still out."""
        with self._connect() as db:
            row = db.execute("SELECT until FROM exhausted WHERE slot = ?", (slot.key,)).fetchone()
        if not row:
            return None
        until = datetime.fromisoformat(row[0])
        return until if until > self._clock() else None

    def resets_at(self, slot: QuotaSlot) -> datetime:
        """Return the instant a slot's current window ends."""
        return window_bounds(slot.window, self._clock())[1]

    def available(self, slot: QuotaSlot, estimated_tokens: int = 0) -> bool:
        """Say whether a slot can take one more call of about estimated_tokens."""
        if self.exhausted_until(slot):
            return False
        requests, tokens = self.usage(slot)
        if slot.max_requests and requests + 1 > slot.max_requests:
            return False
        return not (slot.max_tokens and tokens + estimated_tokens > slot.max_tokens)

    def record(self, slot: QuotaSlot, *, requests: int, tokens: int) -> None:
        """Add what one call spent to its slot's current window."""
        label, _ = window_bounds(slot.window, self._clock())
        with self._connect() as db:
            db.execute(
                "INSERT INTO usage (slot, window, requests, tokens) VALUES (?, ?, ?, ?) "
                "ON CONFLICT (slot, window) DO UPDATE SET requests = requests + excluded.requests, "
                "tokens = tokens + excluded.tokens",
                (slot.key, label, requests, tokens),
            )

    def mark_exhausted(self, slot: QuotaSlot, *, retry_after: float | None = None) -> datetime:
        """Keep a slot out until its window resets, or sooner when the provider said when."""
        now = self._clock()
        until = self.resets_at(slot)
        if retry_after:
            until = min(until, now + timedelta(seconds=retry_after))
        with self._connect() as db:
            db.execute(
                "INSERT INTO exhausted (slot, until) VALUES (?, ?) "
                "ON CONFLICT (slot) DO UPDATE SET until = excluded.until",
                (slot.key, until.isoformat()),
            )
        return until
