"""Read stored human evaluations and aggregate them across stories."""

from __future__ import annotations

import json
import statistics
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

from .evaluation import EVALUATION_FILENAME, METRICS, _load, discover_stories

UNKNOWN = "desconocida"
NO_PROFILE = "sin perfil"


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
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(document, dict):
        return None
    value = document.get(field)
    return value if isinstance(value, str) and value.strip() else None


def _describe(
    directory: Path, stories_root: Path
) -> tuple[str, str, str | None, str | None, str | None]:
    """Collect the grouping axes of one run from its sidecar artifacts."""
    relative = directory.relative_to(stories_root)
    approach = relative.parts[0] if relative.parts else UNKNOWN
    profile = _json_field(directory / "request.json", "narrative_profile")
    generator = _json_field(directory / "generator_version.json", "generator_version")
    pipeline = _json_field(directory / "generator_version.json", "pipeline_version")
    if pipeline is None:
        pipeline = _json_field(directory / "metadata.json", "pipeline_version")
    return relative.as_posix(), approach, profile, generator, pipeline


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
            )
        )
    return records


def _version_of(record: StoryEvaluations) -> str:
    """Pick the version axis that separates generator releases, not pipeline contracts."""
    return record.generator_version or record.pipeline_version or UNKNOWN


def _profile_of(record: StoryEvaluations) -> str:
    """Name the narrative profile of a run that may not declare one."""
    return record.narrative_profile or NO_PROFILE


GROUPINGS: dict[str, Callable[[StoryEvaluations], str]] = {
    "story": lambda record: record.story,
    "profile": _profile_of,
    "version": _version_of,
    "version-profile": lambda record: f"{_version_of(record)} / {_profile_of(record)}",
    "approach": lambda record: record.approach,
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
    grouped: dict[str, list[StoryEvaluations]] = {}
    for record in material:
        grouped.setdefault(key(record), []).append(record)
    return {label: _summary_of(label, grouped[label]) for label in sorted(grouped)}
