"""Horizontal reports use recorded process costs without requiring simulation artifacts."""

import json

import pytest
from asg_evaluation.catalog import digest
from asg_evaluation.feature_audit import compare_with_logs, main
from asg_evaluation.feature_report import read_features
from asg_evaluation.features import measurement
from evaluation_fakes import synthetic_run


def test_direct_prose_costs_are_reported_and_unknown_logs_remain_missing(tmp_path):
    run = synthetic_run(tmp_path / "baseline", 1, baseline=True)
    entry = {
        "call_id": "one",
        "stage": "prose",
        "agent": "writer",
        "model": "fake",
        "total_tokens": 123,
        "duration_seconds": 2.5,
    }
    (run / "llm_calls.jsonl").write_text(json.dumps(entry) + "\n", encoding="utf-8")
    report = read_features(run)
    assert report["features"]["K06"]["value"][0]["tokens"] == 123
    assert report["features"]["K06"]["unit"] == "recuento"
    assert report["features"]["P37"]["status"] == "missing"
    assert report["features"]["P37"]["value"] is None
    assert report["features"]["C01"]["value"] == "Baseline"
    assert report["features"]["T08"]["denominator"] > 0


def _simulated_run(tmp_path, tactics=("lie", "ask"), *, with_log=True):
    """A simulated run whose log has two scenes and one actor turn per tactic."""
    run = synthetic_run(tmp_path / "sim", 1, story_format="simulated")
    if with_log:
        for number, tactic in enumerate(tactics):
            scene = run / "stage" / f"scene-{number % 2}"
            scene.mkdir(parents=True, exist_ok=True)
            row = {"kind": "actor", "actor_id": "ada", "scene_id": scene.name, "speech": "Hola"}
            if tactic:
                row["tactic"] = tactic
            with (scene / "turns.jsonl").open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(row) + "\n")
    (run / "characters.json").write_text(
        json.dumps({"characters": [{"id": "ada", "name": "Ada Lovelace"}]}), encoding="utf-8"
    )
    (run / "simulation_metrics.json").write_text(
        json.dumps({"stage_events": 1, "props": 4, "props_used_ratio": 0.5, "item_actions": 3}),
        encoding="utf-8",
    )
    return run


def _extraction(run, **features):
    """An extraction of the run's text carrying only the given feature measurements."""
    text = (run / "story.md").read_text(encoding="utf-8")
    return {"identity": {"text_hash": digest(text)}, "features": features}


def _pairs(report):
    return {pair["feature"]: pair for pair in report["pairs"]}


def test_lie_turns_feed_p37_only_when_the_run_logged_tactics(tmp_path):
    assert read_features(_simulated_run(tmp_path))["features"]["P37"]["value"] == 1
    old = _simulated_run(tmp_path / "old", tactics=(None, None))
    assert read_features(old)["features"]["P37"]["status"] == "missing"


def test_compare_with_logs_flags_a_text_above_the_ceiling_and_keeps_absences(tmp_path):
    run = _simulated_run(tmp_path)
    extraction = _extraction(
        run,
        X08=measurement(10, raw=5, breakdown={"Ada": {"raw": 5}}),
        X10=measurement(4, raw=4),
        X16=measurement(1),
        X17=measurement(3, raw=3),
        X13=measurement(status="not_applicable", reason="sin secretos"),
    )
    pairs = _pairs(compare_with_logs(extraction, run))
    assert pairs["X10"]["log_value"] == 1 and pairs["X10"]["violates_ceiling"] is True
    assert pairs["X16"]["violates_ceiling"] is False
    actor = pairs["X08"]["by_actor"][0]
    assert (actor["text_label"], actor["text"], actor["log"]) == ("Ada", 5, 2)
    assert actor["violates_ceiling"] is True
    assert pairs["X17"]["log_value"] == 3 and pairs["X17"]["violates_ceiling"] is False
    assert pairs["X13"]["status"] == "not_measured"
    assert pairs["X13"]["reason"] == "sin secretos"
    assert pairs["X18"]["status"] == "not_measured"


def test_compare_with_logs_without_a_log_never_reads_zero(tmp_path):
    run = _simulated_run(tmp_path, with_log=False)
    report = compare_with_logs(_extraction(run, X10=measurement(0, raw=0)), run)
    assert report["logged"] is False
    row = _pairs(report)["X10"]
    assert row["status"] == "not_measured" and row["log_value"] is None
    assert row["violates_ceiling"] is None and row["reason"]


def test_compare_with_logs_rejects_another_text_and_cli_writes_it(tmp_path):
    run = _simulated_run(tmp_path)
    extraction = _extraction(run, X10=measurement(1, raw=1))
    with pytest.raises(ValueError):
        compare_with_logs({"identity": {"text_hash": "otro"}, "features": {}}, run)
    extraction["features"] = {k: measurement(1, raw=1) for k in ("X10",)}
    extraction["features"]["R01"] = measurement(1, raw=1)
    source, output = tmp_path / "x.json", tmp_path / "o.json"
    source.write_text(json.dumps(extraction), encoding="utf-8")
    assert main([str(source), "--run", str(run), "--output", str(output)]) == 0
    written = json.loads(output.read_text(encoding="utf-8"))
    assert _pairs(written["log_comparison"])["X10"]["status"] == "compared"
