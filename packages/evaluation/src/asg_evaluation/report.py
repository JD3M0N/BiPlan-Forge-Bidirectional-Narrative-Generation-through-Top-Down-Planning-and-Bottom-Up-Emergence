"""Read stored human evaluations and aggregate them across stories."""

from __future__ import annotations

import statistics
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

from .artifacts import (
    UNKNOWN,
    group_by,
    load_json_object,
    record_format,
    record_profile,
    record_version,
    text_field,
)
from .evaluation import EVALUATION_FILENAME, METRICS, _load, discover_stories


@dataclass(frozen=True)
class StoryEvaluations:
    """One story directory together with the evaluations stored beside it."""

    directory: Path
    story: str
    run_id: str
    approach: str
    narrative_profile: str | None
    generator_version: str | None
    pipeline_version: str | None
    evaluations: tuple[dict, ...]
    story_format: str = "narrative"
    script_method: str | None = None


@dataclass(frozen=True)
class MetricSummary:
    """Central tendency and spread of one metric over a group of evaluations."""

    metric: str
    count: int
    mean: float | None
    variance: float | None
    stdev: float | None


@dataclass(frozen=True)
class EvaluationSummary:
    """Aggregated scores of every evaluation sharing one grouping key."""

    label: str
    stories: int
    evaluations: int
    metrics: dict[str, MetricSummary]


def read_evaluations(story_directory: str | Path) -> list[dict]:
    """Return the complete evaluations of one story, ignoring pending placeholders.

    A story with no evaluation file yields an empty list; a malformed file raises
    ValueError naming the offending entry.
    """
    destination = Path(story_directory) / EVALUATION_FILENAME
    if not destination.is_file():
        return []
    return _load(destination)


def _json_field(path: Path, field: str) -> str | None:
    """Read one string field from a JSON artifact that may be absent or broken."""
    return text_field(load_json_object(path), field)


def _describe(
    directory: Path, stories_root: Path
) -> tuple[str, str, str | None, str | None, str | None]:
    """Collect the grouping axes of one run from its sidecar artifacts."""
    relative = directory.relative_to(stories_root)
    collection = relative.parts[0] if relative.parts else UNKNOWN
    approach = _approach(directory, collection)
    profile = _json_field(directory / "request.json", "narrative_profile")
    if profile is None:
        # Since 7.2 metadata.json also carries the profile, so a run that failed before its
        # request was analyzed still lands on the profile axis.
        profile = _json_field(directory / "metadata.json", "narrative_profile")
    generator = _json_field(directory / "generator_version.json", "generator_version")
    pipeline = _json_field(directory / "generator_version.json", "pipeline_version")
    if pipeline is None:
        pipeline = _json_field(directory / "metadata.json", "pipeline_version")
    return relative.as_posix(), approach, profile, generator, pipeline


def _approach(directory: Path, collection: str) -> str:
    """Name which of the three approaches produced one run.

    The collection folder is not enough on its own: Stories/Stagecraft holds both top-down runs
    (narrative prose and theater script) and hybrid ones (the characters perform the script and
    the story is narrated from that log), so the format decides. Runs generated before the
    rename keep their own folder and stay grouped as Top-Down, which is what lets the old corpus
    be compared against the new one.
    """
    if collection not in {"Stagecraft", "Top-Down"}:
        return collection
    story_format = _json_field(directory / "metadata.json", "story_format")
    return "Hybrid" if story_format == "simulated" else "Top-Down"


def _output_axes(directory: Path) -> tuple[str, str | None]:
    """Read one run's output format and script method, defaulting to narrative prose."""
    story_format = _json_field(directory / "metadata.json", "story_format") or "narrative"
    script_method = _json_field(directory / "metadata.json", "script_method")
    return story_format, script_method


def collect_evaluations(
    stories_root: str | Path,
    *,
    on_error: Callable[[Path, ValueError], None] | None = None,
) -> list[StoryEvaluations]:
    """Gather every story below a root, including the ones nobody evaluated yet.

    Without ``on_error`` a malformed evaluation file aborts the walk. With it, the file is
    reported and its story is kept with no evaluations, so one bad hand edit cannot hide
    the rest of the corpus.
    """
    root = Path(stories_root)
    records = []
    for directory in discover_stories(root):
        story, approach, profile, generator, pipeline = _describe(directory, root)
        story_format, script_method = _output_axes(directory)
        try:
            evaluations = tuple(read_evaluations(directory))
        except ValueError as error:
            if on_error is None:
                raise
            on_error(directory, error)
            evaluations = ()
        records.append(
            StoryEvaluations(
                directory=directory,
                story=story,
                run_id=directory.name,
                approach=approach,
                narrative_profile=profile,
                generator_version=generator,
                pipeline_version=pipeline,
                evaluations=evaluations,
                story_format=story_format,
                script_method=script_method,
            )
        )
    return records


GROUPINGS: dict[str, Callable[[StoryEvaluations], str]] = {
    "story": lambda record: record.story,
    "profile": record_profile,
    "version": record_version,
    "version-profile": lambda record: f"{record_version(record)} / {record_profile(record)}",
    "approach": lambda record: record.approach,
    "format": record_format,
}


def _summarize_metric(metric: str, scores: Sequence[int]) -> MetricSummary:
    """Summarize one metric using the sample variance, undefined for a single score."""
    if not scores:
        return MetricSummary(metric=metric, count=0, mean=None, variance=None, stdev=None)
    if len(scores) < 2:
        return MetricSummary(
            metric=metric,
            count=len(scores),
            mean=float(scores[0]),
            variance=None,
            stdev=None,
        )
    return MetricSummary(
        metric=metric,
        count=len(scores),
        mean=statistics.fmean(scores),
        variance=statistics.variance(scores),
        stdev=statistics.stdev(scores),
    )


def _summary_of(label: str, records: Sequence[StoryEvaluations]) -> EvaluationSummary:
    """Build the summary of one group by pooling its individual evaluations."""
    evaluations = [item for record in records for item in record.evaluations]
    return EvaluationSummary(
        label=label,
        stories=len(records),
        evaluations=len(evaluations),
        metrics={
            metric: _summarize_metric(metric, [item[metric] for item in evaluations])
            for metric in METRICS
        },
    )


def summarize(
    records: Iterable[StoryEvaluations],
    *,
    key: Callable[[StoryEvaluations], str] | None = None,
) -> dict[str, EvaluationSummary]:
    """Aggregate records into one summary per group, or a single total without a key.

    Groups pool individual evaluations rather than per-story means, so a story evaluated
    twice weighs twice; both counts stay visible on the summary.
    """
    material = [record for record in records if record.evaluations]
    if key is None:
        return {"total": _summary_of("total", material)}
    return {label: _summary_of(label, group) for label, group in group_by(material, key).items()}
