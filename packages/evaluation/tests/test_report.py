import csv
import json

import pytest
from asg_evaluation import (
    GROUPINGS,
    METRICS,
    collect_evaluations,
    read_evaluations,
    summarize,
)
from asg_evaluation.cli import main


def scores(value=8):
    return dict.fromkeys(METRICS, value)


def make_story(root, relative, *, evaluations=None, profile=None, version=None):
    directory = root.joinpath(*relative.split("/"))
    directory.mkdir(parents=True)
    (directory / "story.md").write_text("Historia", encoding="utf-8")
    if profile is not None:
        (directory / "request.json").write_text(
            json.dumps({"narrative_profile": profile}), encoding="utf-8"
        )
    if version is not None:
        (directory / "generator_version.json").write_text(
            json.dumps({"generator_version": version, "pipeline_version": "6.0"}),
            encoding="utf-8",
        )
    if evaluations is not None:
        (directory / "evaluation.json").write_text(
            json.dumps({"schema_version": 1, "evaluations": evaluations}), encoding="utf-8"
        )
    return directory


@pytest.fixture
def corpus(tmp_path):
    stories = tmp_path / "Stories"
    make_story(
        stories,
        "Top-Down/run-a",
        profile="essential",
        version="6.4.1",
        evaluations=[{"user": "ana", **scores(6)}, {"user": "luis", **scores(8)}],
    )
    make_story(
        stories,
        "Top-Down/run-b",
        profile="essential",
        version="6.3.0",
        evaluations=[{"user": "ana", **scores(4)}],
    )
    make_story(
        stories,
        "Top-Down/run-c",
        profile="expansive",
        version="6.4.1",
        evaluations=[{"user": None, **dict.fromkeys(METRICS)}],
    )
    make_story(stories, "Bottom-Up/Escape-Room/run-d", evaluations=[{"user": "ana", **scores(10)}])
    return stories


def test_reading_one_story_ignores_the_pending_template(tmp_path):
    story = make_story(tmp_path, "run", evaluations=[{"user": None, **dict.fromkeys(METRICS)}])
    assert read_evaluations(story) == []
    assert read_evaluations(tmp_path / "missing") == []


def test_collecting_keeps_unevaluated_stories_and_their_axes(corpus):
    records = {record.story: record for record in collect_evaluations(corpus)}
    assert set(records) == {
        "Top-Down/run-a",
        "Top-Down/run-b",
        "Top-Down/run-c",
        "Bottom-Up/Escape-Room/run-d",
    }
    assert records["Top-Down/run-c"].evaluations == ()
    assert records["Top-Down/run-a"].generator_version == "6.4.1"
    assert records["Top-Down/run-a"].pipeline_version == "6.0"
    assert records["Bottom-Up/Escape-Room/run-d"].approach == "Bottom-Up"
    assert records["Bottom-Up/Escape-Room/run-d"].narrative_profile is None


def test_variance_is_undefined_for_a_single_evaluation(corpus):
    by_story = summarize(collect_evaluations(corpus), key=GROUPINGS["story"])
    single = by_story["Top-Down/run-b"].metrics["coherence"]
    assert (single.count, single.mean, single.variance, single.stdev) == (1, 4.0, None, None)
    paired = by_story["Top-Down/run-a"].metrics["coherence"]
    assert (paired.count, paired.mean, paired.variance) == (2, 7.0, 2.0)


def test_profile_and_version_group_the_pooled_evaluations(corpus):
    records = collect_evaluations(corpus)
    by_profile = summarize(records, key=GROUPINGS["profile"])
    assert by_profile["essential"].stories == 2
    assert by_profile["essential"].evaluations == 3
    assert by_profile["essential"].metrics["pacing"].mean == 6.0
    assert by_profile["sin perfil"].metrics["pacing"].mean == 10.0
    by_version = summarize(records, key=GROUPINGS["version"])
    assert sorted(by_version) == ["6.3.0", "6.4.1", "desconocida"]
    combined = summarize(records, key=GROUPINGS["version-profile"])
    assert combined["6.4.1 / essential"].evaluations == 2
    assert summarize(records)["total"].evaluations == 4


def test_the_command_reports_coverage_and_exports_one_row_per_evaluation(corpus, tmp_path, capsys):
    destination = tmp_path / "evaluaciones.csv"
    assert main(["--stories", str(corpus), "--csv", str(destination), "--group", "profile"]) == 0
    printed = capsys.readouterr().out
    assert "4 historias" in printed and "3 con puntuaciones" in printed
    assert "essential" in printed and "sin perfil" in printed
    rows = list(csv.DictReader(destination.read_text(encoding="utf-8").splitlines()))
    assert len(rows) == 4
    first = next(row for row in rows if row["run_id"] == "run-a" and row["user"] == "luis")
    assert first["evaluation_index"] == "2"
    assert first["narrative_profile"] == "essential"
    assert first["generator_version"] == "6.4.1"
    assert first["coherence"] == "8"


def test_a_broken_file_is_reported_without_hiding_the_rest(corpus, capsys):
    broken = corpus / "Top-Down" / "run-b" / "evaluation.json"
    broken.write_text(
        json.dumps({"schema_version": 1, "evaluations": [{"user": "ana", "coherence": 99}]}),
        encoding="utf-8",
    )
    assert main(["--stories", str(corpus), "--group", "profile"]) == 1
    captured = capsys.readouterr()
    assert "evaluación 1: campos desconocidos" not in captured.err
    assert "faltan campos" in captured.err
    assert "run-b" in captured.err
    assert "essential" in captured.out


def test_a_missing_stories_root_is_rejected(tmp_path, capsys):
    assert main(["--stories", str(tmp_path / "nope")]) == 2
    assert "no existe el directorio" in capsys.readouterr().err
