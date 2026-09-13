import csv
import json

import pytest
from asg_evaluation import CRAFT_COLUMNS, collect_story_craft, craft_row, filter_records
from asg_evaluation.craft_cli import main
from asg_evaluation.craft_report import (
    CRAFT_GROUPINGS,
    read_story_craft,
    summarize_craft,
    version_key,
)

DASH = "\u2014"
DRAMATIZED = (
    "# El faro\n\n## El apagon\n\n"
    f"{DASH}La linterna no se apago sola {DASH}dijo Elena.\n\n"
    "El haz muerto dejaba la bahia en sombra.\n"
)
SUMMARIZED = (
    "# La comision\n\n## El informe\n\n"
    "La comision reviso cada guardia y concluyo que nadie subio a la linterna.\n"
)


def make_run(
    root,
    relative,
    *,
    story=DRAMATIZED,
    metadata=None,
    version=None,
    profile=None,
    **sidecars,
):
    directory = root.joinpath(*relative.split("/"))
    directory.mkdir(parents=True)
    if story is not None:
        (directory / "story.md").write_text(story, encoding="utf-8")
    if metadata is not None:
        (directory / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
    if version is not None:
        (directory / "generator_version.json").write_text(
            json.dumps({"generator_version": version, "pipeline_version": "6.1"}),
            encoding="utf-8",
        )
    if profile is not None:
        (directory / "request.json").write_text(
            json.dumps({"narrative_profile": profile}), encoding="utf-8"
        )
    for name, document in sidecars.items():
        text = document if isinstance(document, str) else json.dumps(document)
        (directory / f"{name}.json").write_text(text, encoding="utf-8")
    return directory


def completed(**extra):
    return {
        "status": "completed",
        "model": "gemini-3.5-flash-lite",
        "warnings": [],
        "created_at": "2026-09-13T10:00:00Z",
        "updated_at": "2026-09-13T10:03:20Z",
        **extra,
    }


@pytest.fixture
def corpus(tmp_path):
    stories = tmp_path / "Stories"
    make_run(
        stories,
        "Top-Down/run-new",
        version="6.5.0",
        profile="essential",
        metadata=completed(),
        story_metrics={
            "words": 20,
            "chapters": 1,
            "events": 2,
            "chapter_bodies_recovered": True,
        },
        story_plan={"chapters": [1], "events": [1, 2], "dependencies": []},
        characters={"characters": [1, 2, 3]},
        world={"objects": [1, 2]},
        review={"notes": [1], "strengths": [1, 2], "constraint_checks": []},
        llm_usage={
            "calls": 15,
            "failed_calls": 1,
            "total_tokens": 63028,
            "total_wait_seconds": 0.0,
        },
        narrative_blueprint={"macroplot_id": "quest"},
    )
    make_run(
        stories,
        "Top-Down/run-old",
        version="6.1.0",
        profile="expansive",
        story=SUMMARIZED,
        metadata=completed(warnings=["quality_fallback"]),
    )
    make_run(
        stories,
        "Top-Down/run-legacy",
        story=SUMMARIZED,
        metadata={"status": "completed", "pipeline_version": "5.3"},
    )
    make_run(stories, "Top-Down/run-stalled", version="6.3.0", metadata=completed(status="running"))
    make_run(stories, "Bottom-Up/Escape-Room/run-sim", story=SUMMARIZED)
    make_run(stories, "Top-Down/run-new/craft/variants/variant-1", story=DRAMATIZED)
    return stories


def records_by_story(corpus, **filters):
    records = filter_records(collect_story_craft(corpus), **filters)
    return {record.story: record for record in records}


def test_craft_is_recomputed_for_runs_without_story_metrics(corpus):
    """Measure the prose of a run that never recorded its own craft."""
    records = records_by_story(corpus, minimum_version="6")
    old = records["Top-Down/run-old"]
    assert old.recorded == {}
    assert old.craft.paragraphs == 1
    assert old.craft.dialogue_paragraphs == 0
    assert old.craft.words_per_paragraph > 0
    new = records["Top-Down/run-new"]
    assert new.recorded["words"] == 20
    assert new.craft.dash_paragraphs == 1
    assert new.craft.dialogue_ratio == 0.5


def test_every_declared_column_is_written_once_per_run(corpus):
    """Keep the row exactly as wide as the declared header."""
    record = records_by_story(corpus, minimum_version="6")["Top-Down/run-new"]
    row = craft_row(record)
    assert len(row) == len(CRAFT_COLUMNS)
    values = dict(zip(CRAFT_COLUMNS, row, strict=True))
    assert values["generator_version"] == "6.5.0"
    assert values["has_story_metrics"] == 1
    assert values["metrics_events"] == 2
    assert values["plan_dependencies"] == 0
    assert values["characters"] == 3
    assert values["world_objects"] == 2
    assert values["review_notes"] == 1
    assert values["llm_total_tokens"] == 63028
    assert values["blueprint_macroplot"] == "quest"
    assert values["duration_seconds"] == 200.0
    assert values["warnings"] == 0


def test_missing_sidecar_artifacts_leave_empty_columns_without_failing(corpus):
    """Never invent a zero for an artifact the run does not have."""
    record = records_by_story(corpus, minimum_version="6")["Top-Down/run-old"]
    values = dict(zip(CRAFT_COLUMNS, craft_row(record), strict=True))
    assert values["has_story_metrics"] == 0
    assert values["metrics_words"] == ""
    assert values["chapter_bodies_recovered"] == ""
    assert values["plan_chapters"] == ""
    assert values["llm_calls"] == ""
    assert values["warnings"] == 1


def test_the_minimum_version_filter_drops_older_and_unversioned_runs(corpus):
    """Resolve the six-onwards question with a tuple comparison, not a string one."""
    assert set(records_by_story(corpus, minimum_version="6")) == {
        "Top-Down/run-new",
        "Top-Down/run-old",
        "Top-Down/run-stalled",
    }
    assert "Top-Down/run-legacy" in records_by_story(corpus, minimum_version="5")
    assert version_key("6.4.1") > version_key("6.4") > version_key("6")
    assert version_key(None) == ()
    assert version_key("") == ()


def test_bottom_up_and_nested_stories_are_excluded_by_the_default_filter(corpus):
    """Leave the runs that declare no version out until somebody asks for them."""
    default = records_by_story(corpus, minimum_version="6")
    assert "Bottom-Up/Escape-Room/run-sim" not in default
    assert all("variant-1" not in story for story in default)
    everything = records_by_story(corpus, minimum_version="0", include_unversioned=True)
    assert "Bottom-Up/Escape-Room/run-sim" in everything
    assert "Top-Down/run-new/craft/variants/variant-1" in everything


def test_nested_story_directories_keep_a_unique_relative_key(corpus):
    """Use the relative path as the key, because a run id can repeat."""
    everything = records_by_story(corpus, minimum_version="0", include_unversioned=True)
    nested = everything["Top-Down/run-new/craft/variants/variant-1"]
    assert nested.run_id == "variant-1"
    assert len(everything) == 6


def test_the_pipeline_version_fallback_places_a_run_on_the_version_axis(corpus):
    """Fall back to the pipeline contract when no generator version was written."""
    legacy = records_by_story(corpus, minimum_version="5")["Top-Down/run-legacy"]
    assert legacy.generator_version is None
    assert legacy.pipeline_version == "5.3"
    assert CRAFT_GROUPINGS["version"](legacy) == "5.3"
    assert CRAFT_GROUPINGS["profile"](legacy) == "sin perfil"


def test_running_and_failed_runs_reach_the_csv_but_not_the_summary(corpus, tmp_path, capsys):
    """Keep unfinished runs in the data and out of the medians."""
    destination = tmp_path / "craft.csv"
    assert main(["--stories", str(corpus), "--csv", str(destination), "--group", "version"]) == 0
    printed = capsys.readouterr().out
    rows = list(csv.DictReader(destination.read_text(encoding="utf-8").splitlines()))
    assert {row["run_id"] for row in rows} == {"run-new", "run-old", "run-stalled"}
    assert next(row for row in rows if row["run_id"] == "run-stalled")["status"] == "running"
    assert "6.3.0" not in printed
    assert "6.5.0" in printed
    assert "6.1.0" in printed
    assert "3 en el informe, 2 en el resumen" in printed


def test_a_broken_json_artifact_is_reported_without_hiding_the_rest(corpus, capsys):
    """Report one unreadable sidecar and keep every other story."""
    (corpus / "Top-Down" / "run-old" / "story_metrics.json").write_text("{roto", encoding="utf-8")
    assert main(["--stories", str(corpus), "--group", "profile"]) == 1
    captured = capsys.readouterr()
    assert "story_metrics.json" in captured.err
    assert "essential" in captured.out
    assert "expansive" in captured.out


def test_the_summary_reports_median_and_counts_stories_without_dialogue(corpus):
    """Give the long tail a median and the silent stories their own counter."""
    records = filter_records(collect_story_craft(corpus), minimum_version="6", completed_only=True)
    summaries = summarize_craft(records, key=CRAFT_GROUPINGS["profile"])
    assert summaries["essential"].without_dialogue == 0
    assert summaries["expansive"].without_dialogue == 1
    ratio = summaries["expansive"].stats["dialogue_ratio"]
    assert (ratio.count, ratio.median, ratio.maximum) == (1, 0.0, 0.0)
    total = summarize_craft(records)["total"]
    assert total.stories == 2
    assert total.stats["dialogue_ratio"].median == 0.25


def test_a_missing_stories_root_is_rejected(tmp_path, capsys):
    """Refuse to report over a root that does not exist."""
    assert main(["--stories", str(tmp_path / "nope")]) == 2
    assert "no existe el directorio" in capsys.readouterr().err


def test_a_story_that_cannot_be_read_is_reported_as_empty_prose(corpus):
    """Keep the corpus walk alive when one story file is unreadable."""
    directory = corpus / "Top-Down" / "run-empty"
    directory.mkdir()
    (directory / "story.md").write_bytes(b"\xff\xfe\x00 no es utf-8")
    reported = []
    record = read_story_craft(directory, corpus, on_error=lambda path, error: reported.append(path))
    assert record.craft.paragraphs == 0
    assert record.craft.dialogue_ratio == 0.0
    assert reported == [directory / "story.md"]
