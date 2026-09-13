"""Spanish formatting helpers shared by the evaluation reports."""

from __future__ import annotations

UNDEFINED = "\u2014"


def count_noun(amount: int, singular: str, plural: str) -> str:
    """Join a count with the Spanish noun form it requires."""
    return f"{amount} {singular if amount == 1 else plural}"


def format_number(value: float | None, digits: int = 2) -> str:
    """Format an optional statistic, marking the ones no sample can define."""
    return UNDEFINED if value is None else f"{value:.{digits}f}"
