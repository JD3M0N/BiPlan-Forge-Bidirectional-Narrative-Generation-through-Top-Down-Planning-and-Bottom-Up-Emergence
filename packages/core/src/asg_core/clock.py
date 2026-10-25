"""The one timestamp every audit column in the monorepo is written with."""

from datetime import UTC, datetime


def audit_timestamp() -> str:
    """Return the current instant as a timezone-aware ISO string.

    Rows that record who answered what, and when, are compared across the bot, the study and
    the artifacts on disk, so they are all stamped in UTC from here rather than in local time
    wherever the row happens to be written.
    """
    return datetime.now(UTC).isoformat()
