"""Recompute prose craft over a story corpus and pair it with the metadata of each run."""

from __future__ import annotations

import json
import statistics
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from asg_core import CraftMetrics, craft_metrics

from .evaluation import discover_stories
from .report import NO_PROFILE, UNKNOWN, _describe

STORY_FILENAME = "story.md"
METRICS_FILENAME = "story_metrics.json"
ErrorHandler = Callable[[Path, str], None]


@dataclass(frozen=True)
class RunCounts:
    """Sidecar counts describing the plan, the review and the model usage of one run."""

    plan_chapters: int | None
    plan_events: int | None
    plan_dependencies: int | None
    characters: int | None
    world_objects: int | None
    review_notes: int | None
    review_strengths: int | None
    constraint_checks: int | None
    llm_calls: int | None
    llm_failed_calls: int | None
    llm_total_tokens: int | None
    llm_total_wait_seconds: float | None


@dataclass(frozen=True)
class StoryCraft:
    """Craft figures of one story together with every axis available beside it."""

    directory: Path
    story: str
    run_id: str
    approach: str
    narrative_profile: str | None
    generator_version: str | None
    pipeline_version: str | None
    status: str | None
    model: str | None
    warnings: int
    created_at: str | None
    updated_at: str | None
    duration_seconds: float | None
    craft: CraftMetrics
    recorded: dict
    counts: RunCounts
    blueprint_macroplot: str | None


@dataclass(frozen=True)
class CraftStat:
    """Central tendency and range of one craft figure over a group of stories."""

    field: str
    count: int
    mean: float | None
    median: float | None
    minimum: float | None
    maximum: float | None


@dataclass(frozen=True)
class CraftSummary:
    """Craft figures of every story sharing one grouping key."""

    label: str
    stories: int
    without_dialogue: int
    stats: dict[str, CraftStat]


CRAFT_FIELDS = (
    "dialogue_ratio",
    "words_per_sentence",
    "words_per_paragraph",
    "words",
    "paragraphs",
)

CRAFT_COLUMNS = (
    "approach",
    "story",
    "run_id",
    "narrative_profile",
    "generator_version",
    "pipeline_version",
    "status",
    "model",
    "warnings",
    "created_at",
    "updated_at",
    "duration_seconds",
    "prose_paragraphs",
    "prose_sentences",
    "prose_words",
    "dash_paragraphs",
    "quoted_paragraphs",
    "dialogue_paragraphs",
    "dialogue_ratio",
    "words_per_sentence",
    "words_per_paragraph",
    "has_story_metrics",
    "metrics_words",
    "metrics_chapters",
    "metrics_events",
    "chapter_bodies_recovered",
    "plan_chapters",
    "plan_events",
    "plan_dependencies",
    "characters",
    "world_objects",
    "review_notes",
    "review_strengths",
    "constraint_checks",
    "llm_calls",
    "llm_failed_calls",
    "llm_total_tokens",
    "llm_total_wait_seconds",
    "blueprint_macroplot",
)


def _load_document(path: Path, on_error: ErrorHandler | None) -> dict:
    """Read one JSON artifact, reporting a broken or unreadable file as empty."""
    if not path.is_file():
        return {}
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        if on_error is not None:
            on_error(path, str(error))
        return {}
    return document if isinstance(document, dict) else {}


def _read_story(directory: Path, on_error: ErrorHandler | None) -> str:
    """Read the Markdown of one story, reporting an unreadable file as empty."""
    path = directory / STORY_FILENAME
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        if on_error is not None:
            on_error(path, str(error))
        return ""


def _length(document: dict, field: str) -> int | None:
    """Count the entries of one list field, or None when it is absent."""
    value = document.get(field)
    return len(value) if isinstance(value, list) else None


def _integer(document: dict, field: str) -> int | None:
    """Read one integer field, ignoring booleans and non-numeric values."""
    value = document.get(field)
    return int(value) if isinstance(value, int) and not isinstance(value, bool) else None


def _decimal(document: dict, field: str) -> float | None:
    """Read one numeric field as a float, ignoring booleans and other types."""
    value = document.get(field)
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value)


def _text(document: dict, field: str) -> str | None:
    """Read one non-empty string field, or None when it is absent."""
    value = document.get(field)
    return value if isinstance(value, str) and value.strip() else None


def _wall_duration(metadata: dict) -> float | None:
    """Measure the wall-clock seconds between the first and the last metadata write."""
    started, ended = _text(metadata, "created_at"), _text(metadata, "updated_at")
    if started is None or ended is None:
        return None
    try:
        elapsed = datetime.fromisoformat(ended) - datetime.fromisoformat(started)
    except ValueError:
        return None
    return round(elapsed.total_seconds(), 3)


def _run_counts(directory: Path, on_error: ErrorHandler | None) -> RunCounts:
    """Collect the countable sidecar artifacts of one run."""
    plan = _load_document(directory / "story_plan.json", on_error)
    characters = _load_document(directory / "characters.json", on_error)
    world = _load_document(directory / "world.json", on_error)
    review = _load_document(directory / "review.json", on_error)
    usage = _load_document(directory / "llm_usage.json", on_error)
    return RunCounts(
        plan_chapters=_length(plan, "chapters"),
        plan_events=_length(plan, "events"),
        plan_dependencies=_length(plan, "dependencies"),
        characters=_length(characters, "characters"),
        world_objects=_length(world, "objects"),
        review_notes=_length(review, "notes"),
        review_strengths=_length(review, "strengths"),
        constraint_checks=_length(review, "constraint_checks"),
        llm_calls=_integer(usage, "calls"),
        llm_failed_calls=_integer(usage, "failed_calls"),
        llm_total_tokens=_integer(usage, "total_tokens"),
        llm_total_wait_seconds=_decimal(usage, "total_wait_seconds"),
    )


def read_story_craft(
    directory: str | Path,
    stories_root: str | Path,
    *,
    on_error: ErrorHandler | None = None,
) -> StoryCraft:
    """Measure one story directory and gather every metadata axis beside it."""
    run_dir, root = Path(directory), Path(stories_root)
    story, approach, profile, generator, pipeline = _describe(run_dir, root)
    metadata = _load_document(run_dir / "metadata.json", on_error)
    blueprint = _load_document(run_dir / "narrative_blueprint.json", on_error)
    return StoryCraft(
        directory=run_dir,
        story=story,
        run_id=run_dir.name,
        approach=approach,
        narrative_profile=profile,
        generator_version=generator,
        pipeline_version=pipeline,
        status=_text(metadata, "status"),
        model=_text(metadata, "model"),
        warnings=len(metadata.get("warnings") or []),
        created_at=_text(metadata, "created_at"),
        updated_at=_text(metadata, "updated_at"),
        duration_seconds=_wall_duration(metadata),
        craft=craft_metrics(_read_story(run_dir, on_error)),
        recorded=_load_document(run_dir / METRICS_FILENAME, on_error),
        counts=_run_counts(run_dir, on_error),
        blueprint_macroplot=_text(blueprint, "macroplot_id"),
    )


def collect_story_craft(
    stories_root: str | Path,
    *,
    on_error: ErrorHandler | None = None,
) -> list[StoryCraft]:
    """Measure every story below a root, unfiltered and in discovery order."""
    root = Path(stories_root)
    return [
        read_story_craft(directory, root, on_error=on_error) for directory in discover_stories(root)
    ]


def version_key(version: str | None) -> tuple[int, ...]:
    """Turn a dotted version into a comparable tuple, empty when undeclared."""
    if not version:
        return ()
    parts: list[int] = []
    for piece in version.split("."):
        if not piece.isdigit():
            break
        parts.append(int(piece))
    return tuple(parts)


def record_version(record: StoryCraft) -> str:
    """Pick the version axis that separates generator releases, not pipeline contracts."""
    return record.generator_version or record.pipeline_version or UNKNOWN


def record_profile(record: StoryCraft) -> str:
    """Name the narrative profile of a run that may not declare one."""
    return record.narrative_profile or NO_PROFILE


CRAFT_GROUPINGS: dict[str, Callable[[StoryCraft], str]] = {
    "story": lambda record: record.story,
    "profile": record_profile,
    "version": record_version,
    "version-profile": lambda record: f"{record_version(record)} / {record_profile(record)}",
    "approach": lambda record: record.approach,
    "status": lambda record: record.status or UNKNOWN,
}


def filter_records(
    records: Iterable[StoryCraft],
    *,
    minimum_version: str | None = None,
    approach: str | None = None,
    include_unversioned: bool = False,
    completed_only: bool = False,
) -> list[StoryCraft]:
    """Keep the records that belong in one report, by version, approach and status.

    ``completed_only`` drops the runs that declare an unfinished status, and keeps the
    ones that declare none at all: a run without ``metadata.json`` never claimed to fail.
    """
    floor = version_key(minimum_version)
    selected = []
    for record in records:
        declared = version_key(record.generator_version or record.pipeline_version)
        if not declared:
            if not include_unversioned:
                continue
        elif declared < floor:
            continue
        if approach is not None and record.approach != approach:
            continue
        if completed_only and record.status not in (None, "completed"):
            continue
        selected.append(record)
    return selected


def craft_row(record: StoryCraft) -> list[object]:
    """Flatten one measured story into its declared CSV columns."""
    craft, counts, recorded = record.craft, record.counts, record.recorded
    values: list[object] = [
        record.approach,
        record.story,
        record.run_id,
        record.narrative_profile,
        record.generator_version,
        record.pipeline_version,
        record.status,
        record.model,
        record.warnings,
        record.created_at,
        record.updated_at,
        record.duration_seconds,
        craft.paragraphs,
        craft.sentences,
        craft.words,
        craft.dash_paragraphs,
        craft.quoted_paragraphs,
        craft.dialogue_paragraphs,
        craft.dialogue_ratio,
        craft.words_per_sentence,
        craft.words_per_paragraph,
        int(bool(recorded)),
        _integer(recorded, "words"),
        _integer(recorded, "chapters"),
        _integer(recorded, "events"),
        recorded.get("chapter_bodies_recovered"),
        counts.plan_chapters,
        counts.plan_events,
        counts.plan_dependencies,
        counts.characters,
        counts.world_objects,
        counts.review_notes,
        counts.review_strengths,
        counts.constraint_checks,
        counts.llm_calls,
        counts.llm_failed_calls,
        counts.llm_total_tokens,
        counts.llm_total_wait_seconds,
        record.blueprint_macroplot,
    ]
    return ["" if value is None else value for value in values]


def _stat(field: str, values: Sequence[float]) -> CraftStat:
    """Summarize one craft figure with its central tendency and its range."""
    if not values:
        return CraftStat(field=field, count=0, mean=None, median=None, minimum=None, maximum=None)
    return CraftStat(
        field=field,
        count=len(values),
        mean=statistics.fmean(values),
        median=statistics.median(values),
        minimum=min(values),
        maximum=max(values),
    )


def _summary_of(label: str, records: Sequence[StoryCraft]) -> CraftSummary:
    """Build the summary of one group from the craft figures of its stories."""
    return CraftSummary(
        label=label,
        stories=len(records),
        without_dialogue=sum(1 for item in records if item.craft.dialogue_paragraphs == 0),
        stats={
            field: _stat(field, [getattr(item.craft, field) for item in records])
            for field in CRAFT_FIELDS
        },
    )


def summarize_craft(
    records: Iterable[StoryCraft],
    *,
    key: Callable[[StoryCraft], str] | None = None,
) -> dict[str, CraftSummary]:
    """Aggregate records into one summary per group, or a single total without a key."""
    material = list(records)
    if key is None:
        return {"total": _summary_of("total", material)}
    grouped: dict[str, list[StoryCraft]] = {}
    for record in material:
        grouped.setdefault(key(record), []).append(record)
    return {label: _summary_of(label, grouped[label]) for label in sorted(grouped)}
