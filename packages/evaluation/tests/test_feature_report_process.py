"""Horizontal reports use recorded process costs without requiring simulation artifacts."""

import json

from asg_evaluation.demo import synthetic_run
from asg_evaluation.feature_report import read_features


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
