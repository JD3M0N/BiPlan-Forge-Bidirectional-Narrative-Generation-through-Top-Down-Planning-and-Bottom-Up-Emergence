import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from asg_evaluation import corpus

NOW = datetime(2026, 10, 28, tzinfo=UTC)


def make_run(
    root: Path,
    name: str,
    *,
    family: str = "Stagecraft",
    metadata: dict | None = None,
    story: bool = True,
    version_file: bool = True,
) -> Path:
    run = root / family / name
    run.mkdir(parents=True)
    base = {"status": "completed", "story_format": "narrative", "pipeline_version": "7.22"}
    (run / "metadata.json").write_text(
        json.dumps({k: v for k, v in {**base, **(metadata or {})}.items() if v is not None}),
        encoding="utf-8",
    )
    if story:
        (run / "story.md").write_text("# Historia\n\nTexto.", encoding="utf-8")
    if version_file:
        (run / "generator_version.json").write_text(
            json.dumps({"generator_version": "7.22.0"}), encoding="utf-8"
        )
    return run


def kinds(report: dict) -> set[str]:
    return {a["kind"] for a in report["anomalies"]}


@pytest.mark.parametrize(
    ("metadata", "story", "reason"),
    [
        ({}, True, ""),
        ({"story_format": "simulated"}, True, ""),
        ({"story_format": "baseline"}, True, ""),
        ({"status": "failed"}, True, "Run no completado"),
        ({"status": "running"}, True, "Run no completado"),
        ({}, False, "Sin story.md"),
        ({"story_format": "script"}, True, "Formato fuera del estudio en prosa"),
        ({"pipeline_version": "6.6"}, True, "Generador anterior a Stagecraft 7"),
        ({"pipeline_version": None}, True, "Generador anterior a Stagecraft 7"),
    ],
)
def test_each_exclusion_reason(tmp_path, metadata, story, reason):
    make_run(tmp_path, "run", metadata=metadata, story=story)
    row = corpus.scan(tmp_path, NOW)["runs"][0]
    assert row["reason"] == reason and row["eligible"] == (not reason)


@pytest.mark.parametrize(
    ("kind", "build"),
    [
        (
            "sin_version_de_pipeline",
            lambda r: make_run(r, "a", metadata={"pipeline_version": None}),
        ),
        ("sin_generator_version", lambda r: make_run(r, "a", version_file=False)),
        ("formato_inferido", lambda r: make_run(r, "a", metadata={"story_format": None})),
        ("failed_con_story", lambda r: make_run(r, "a", metadata={"status": "failed"})),
        (
            "running_atascado",
            lambda r: make_run(
                r, "a", metadata={"status": "running", "updated_at": "2026-10-02T15:00:00Z"}
            ),
        ),
        ("tmp_suelto", lambda r: (make_run(r, "a") / ".story.mp3.x.tmp").write_text("x")),
        (
            "no_es_run",
            lambda r: (r / "Top-Down").mkdir() or (r / "Top-Down" / "a.html").write_text(""),
        ),
    ],
)
def test_each_anomaly_is_listed(tmp_path, kind, build):
    build(tmp_path)
    assert kind in kinds(corpus.scan(tmp_path, NOW))


def test_clean_run_has_no_anomalies_and_recent_running_is_not_stuck(tmp_path):
    make_run(tmp_path, "ok")
    make_run(
        tmp_path,
        "live",
        metadata={"status": "running", "updated_at": "2026-10-27T20:00:00Z"},
    )
    assert "running_atascado" not in kinds(corpus.scan(tmp_path, NOW))
    assert kinds(corpus.scan(tmp_path, NOW)) == set()


def test_nested_runs_are_found_and_empty_folders_flagged(tmp_path):
    make_run(tmp_path, "run", family="Bottom-Up/Escape-Room", metadata={"pipeline_version": None})
    (tmp_path / "Bottom-Up" / "Escape-Room" / "experiments" / "x").mkdir(parents=True)
    (tmp_path / "Bottom-Up" / ".gitkeep").write_text("")
    report = corpus.scan(tmp_path, NOW)
    assert [r["run"] for r in report["runs"]] == ["Bottom-Up/Escape-Room/run"]
    assert report["runs"][0]["family"] == "Bottom-Up"
    assert [a["path"] for a in report["anomalies"] if a["kind"] == "no_es_run"] == [
        "Bottom-Up/Escape-Room/experiments"
    ]


def test_cli_writes_json_and_csv_without_touching_the_corpus(tmp_path, capsys):
    make_run(tmp_path / "Stories", "ok")
    before = sorted(p.name for p in (tmp_path / "Stories").rglob("*"))
    out_json, out_csv = tmp_path / "inv.json", tmp_path / "inv.csv"
    code = corpus.main([str(tmp_path / "Stories"), "--json", str(out_json), "--csv", str(out_csv)])
    assert (
        code == 0 and json.loads(out_json.read_text(encoding="utf-8"))["summary"]["eligible"] == 1
    )
    assert out_csv.read_text(encoding="utf-8").startswith("run,family")
    assert sorted(p.name for p in (tmp_path / "Stories").rglob("*")) == before
    assert corpus.main([str(tmp_path / "missing")]) == 1
    capsys.readouterr()
