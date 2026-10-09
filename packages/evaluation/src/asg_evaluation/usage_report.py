"""Where a run's model calls went: calls, attempts, tokens and latency by agent and stage.

Reads only llm_calls.jsonl, like the rest of this package. Since 7.2 every record names the
pipeline stage and the agent that made it, and every attempt of one logical call shares its
call_id; a run written before that has no agent, and its split is reported as not measured,
never folded into an anonymous agent.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from .artifacts import group_by, load_json_object, read_json_lines, text_field
from .report import _approach

CALLS_FILENAME = "llm_calls.jsonl"
UNKNOWN = "desconocida"
# The keys every aggregated row carries, beyond the ones it is grouped by.
USAGE_FIELDS = ("calls", "attempts", "failed_attempts", "tokens", "latency_seconds", "wait_seconds")


def aggregate_calls(items: Iterable[dict], keys: tuple[str, ...]) -> list[dict]:
    """Sum logical calls, attempts, tokens, latency and waiting per combination of keys.

    A token count is no call, and a record without call_id cannot be regrouped, so neither
    counts. Rows come back sorted by their keys.
    """
    groups: dict[tuple[str, ...], dict] = {}
    for item in items:
        if item.get("operation") == "count_tokens" or not item.get("call_id"):
            continue
        key = tuple(str(item.get(name) or "") for name in keys)
        group = groups.setdefault(
            key,
            {
                **dict(zip(keys, key, strict=True)),
                "call_ids": set(),
                "attempts": 0,
                "failed_attempts": 0,
                "tokens": 0,
                "latency_seconds": 0.0,
                "wait_seconds": 0.0,
            },
        )
        group["call_ids"].add(item["call_id"])
        group["attempts"] += 1
        group["failed_attempts"] += item.get("status") != "succeeded"
        group["tokens"] += item.get("total_tokens") or 0
        group["latency_seconds"] += item.get("duration_seconds") or 0.0
        group["wait_seconds"] += item.get("wait_seconds") or 0.0
    rows = []
    for _, group in sorted(groups.items()):
        call_ids = group.pop("call_ids")
        rows.append(
            {
                **group,
                "calls": len(call_ids),
                "latency_seconds": round(group["latency_seconds"], 3),
                "wait_seconds": round(group["wait_seconds"], 3),
            }
        )
    return rows


@dataclass
class UsageRecord:
    """One run's call log, split by stage and agent, or None where it was not recorded."""

    directory: Path
    run_id: str
    approach: str
    generator_version: str
    status: str
    rows: list[dict] | None


def read_usage(directory: Path, stories_root: Path) -> UsageRecord:
    """Describe one run's spending; a log without agents is not measured."""
    items = [
        item
        for item in read_json_lines(directory / CALLS_FILENAME)
        if item.get("operation") != "count_tokens"
    ]
    metadata = load_json_object(directory / "metadata.json")
    generator = load_json_object(directory / "generator_version.json")
    collection = directory.relative_to(stories_root).parts[0]
    measured = bool(items) and all("agent" in item for item in items)
    return UsageRecord(
        directory=directory,
        run_id=directory.name,
        approach=_approach(directory, collection),
        generator_version=text_field(generator, "generator_version")
        or text_field(metadata, "pipeline_version")
        or UNKNOWN,
        status=text_field(metadata, "status") or UNKNOWN,
        rows=aggregate_calls(items, ("stage", "agent")) if measured else None,
    )


def collect_usage(stories_root: str | Path) -> list[UsageRecord]:
    """Read every run that has a call log below a stories root, in a stable order."""
    root = Path(stories_root)
    if not root.is_dir():
        return []
    directories = sorted({path.parent for path in root.rglob(CALLS_FILENAME) if path.is_file()})
    return [read_usage(directory, root) for directory in directories]


def summarize_usage(records: Iterable[UsageRecord], key: str) -> list[dict]:
    """Add the measured runs' rows up by agent or by stage, with each one's share of calls."""
    rows = [
        {key: row[key] or "(sin nombre)", **{name: row[name] for name in USAGE_FIELDS}}
        for record in records
        if record.rows is not None
        for row in record.rows
    ]
    totals = []
    for label, group in group_by(rows, lambda row: row[key]).items():
        total = {key: label}
        for name in USAGE_FIELDS:
            total[name] = sum(row[name] for row in group)
        totals.append(total)
    calls = sum(total["calls"] for total in totals)
    for total in totals:
        total["latency_seconds"] = round(total["latency_seconds"], 3)
        total["wait_seconds"] = round(total["wait_seconds"], 3)
        total["call_share"] = total["calls"] / calls if calls else None
    return sorted(totals, key=lambda total: (-total["calls"], total[key]))
