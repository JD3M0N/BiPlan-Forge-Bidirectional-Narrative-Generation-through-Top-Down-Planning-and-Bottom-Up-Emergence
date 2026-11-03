"""Statistical integrity of preference aggregation and held-out preprocessing."""

import json
import re
import statistics
from itertools import combinations
from pathlib import Path

import numpy as np
import pytest
from asg_evaluation import learning_cli
from asg_evaluation.catalog import prompt_work, resource_text
from asg_evaluation.feature_report import read_features, study_extractions
from asg_evaluation.features import extract_features
from asg_evaluation.judge import (
    _validate,
    collinearity,
    fit_linear,
    perturbation_report,
    predict,
    rank_features,
    story_marks,
    train_judge,
)
from asg_evaluation.learning_cli import load_study_features, top_ten_sheet
from asg_evaluation.perturbation import blocks, no_ending, shuffled
from asg_evaluation.perturbation import main as perturb_main
from asg_evaluation.preferences import agreement, bradley_terry, decided_votes
from evaluation_fakes import SyntheticProvider, voted_study


def sample():
    vectors = {str(i): [float(i), None if i == 1 else float(i * 2)] for i in range(6)}
    vectors["5"] = [10000.0, 20000.0]
    votes = [
        {
            "id": str(i),
            "participant": "reader",
            "criterion": "H01",
            "left": a,
            "right": b,
            "choice": "B",
        }
        for i, (a, b) in enumerate(combinations(vectors, 2))
    ]
    return vectors, votes


def test_held_out_stories_and_all_their_votes_are_absent_from_preprocessing():
    vectors, votes = sample()
    result = _validate(vectors, votes, ["T01", "R01"], {s: s for s in vectors})
    assert result["tested_votes"] == len(votes)
    for fold in result["folds"]:
        held = set(fold["held_out"])
        assert held.isdisjoint(fold["training_stories"])
        train = [v for v in votes if v["id"] in fold["train_vote_ids"]]
        assert all(held.isdisjoint((v["left"], v["right"])) for v in train)
        raw = np.array([vectors[s] for s in fold["training_stories"]], dtype=float)
        assert np.allclose(fold["medians"], np.nanmedian(raw, axis=0))
        filled = np.where(np.isfinite(raw), raw, fold["medians"])
        assert np.allclose(fold["means"], filled.mean(axis=0))
    extreme = next(f for f in result["folds"] if f["held_out"] == ["5"])
    assert max(extreme["means"]) < 10


def test_families_are_held_out_together_and_linear_scores_are_antisymmetric():
    vectors, votes = sample()
    groups = {s: str(int(s) // 2) for s in vectors}
    result = _validate(vectors, votes, ["T01", "R01"], groups)
    assert all(len(f["held_out"]) == 2 for f in result["folds"])
    fitted = fit_linear(vectors, votes, ["T01", "R01"])
    assert "intercept" not in fitted
    a, b = predict(fitted, vectors["0"]), predict(fitted, vectors["5"])
    assert a - b == -(b - a)
    with pytest.raises(ValueError):
        fit_linear(vectors, votes[:1], ["T01", "R01"])


def test_collinearity_lists_identical_and_constant_features():
    vectors, votes = sample()
    vectors = {s: [v[0], v[0], 3.0, (int(s) * 7) % 5] for s, v in vectors.items()}
    result = collinearity(vectors, votes, ["T01", "T02", "K01", "R01"])
    assert result["constant_features"] == ["K01"]
    assert (result["pairs"][0]["a"], result["pairs"][0]["b"]) == ("T01", "T02")
    assert result["pairs"][0]["r"] == pytest.approx(1.0)
    assert result["condition_number"] is None  # exactly singular
    vectors = {s: [v[0], v[3]] for s, v in vectors.items()}
    assert collinearity(vectors, votes, ["T01", "R01"])["condition_number"] >= 1


def test_family_baseline_keeps_families_together_and_reports_coverage():
    vectors, votes = sample()
    families = {s: "f" + str(int(s) // 3) for s in vectors}
    result = _validate(vectors, votes, ["T01", "R01"], families)
    assert sorted(tuple(f["held_out"]) for f in result["folds"]) == [
        ("0", "1", "2"),
        ("3", "4", "5"),
    ]
    assert result["coverage"] == result["tested_votes"] / result["total_votes"] == 1.0
    assert _validate(vectors, [], ["T01"], families)["coverage"] is None


def test_abstention_does_not_connect_graph_and_agreement_normalizes_orientation():
    votes = [
        {"left": "a", "right": "b", "choice": "A", "participant": "p1", "criterion": "H01"},
        {"left": "b", "right": "a", "choice": "B", "participant": "p2", "criterion": "H01"},
        {"left": "b", "right": "c", "choice": "abstain", "participant": "p1", "criterion": "H01"},
    ]
    result = bradley_terry(["a", "b", "c"], decided_votes(votes))
    assert result["status"] == "insufficient" and result["ranking"] == []
    result = agreement(votes)
    assert result["agreement"] == 1.0


def test_public_commands_reuse_study_extractions_and_reject_mixed_protocols(tmp_path):
    study = voted_study(tmp_path)
    provider = SyntheticProvider()
    for story in study.export()["stories"]:
        extract_features(
            story["text"],
            provider,
            model="fake",
            output=tmp_path / "features" / f"{story['id']}.json",
        )
    db, runs = tmp_path / "study.sqlite3", str(tmp_path / "runs")
    judge_path, ranking_path = tmp_path / "judge.json", tmp_path / "ranking.json"
    assert learning_cli.human_main([str(db), "--output", str(tmp_path / "human.json")]) == 0
    assert learning_cli.train_main([str(db), "--output", str(judge_path)]) == 0
    assert (
        learning_cli.rank_main(
            [str(judge_path), runs, "--study", str(db), "--output", str(ranking_path)]
        )
        == 0
    )
    ranking = json.loads(ranking_path.read_text(encoding="utf-8"))
    assert ranking["excluded"] == [] and len(ranking["rankings"]["H01"]) == 6
    features = load_study_features(study)
    story = next(iter(features))
    features[story]["identity"]["model"] = "other-model"
    with pytest.raises(ValueError, match="protocolos"):
        train_judge(study.export(), features)
    sidecar = tmp_path / "features" / f"{story}.json"
    sidecar.write_text(json.dumps(features[story]), encoding="utf-8")
    extractions = study_extractions(db)
    rows = [
        read_features(p.parent, extractions=extractions)
        for p in (tmp_path / "runs").rglob("story.md")
    ]
    judge = json.loads(judge_path.read_text(encoding="utf-8"))
    fitted = judge["criteria"]["H01"]
    assert set(fitted["length_baseline"]) == {"by_story", "by_family"}
    assert "coverage" in fitted["family_validation"] and "pairs" in fitted["collinearity"]
    excluded = rank_features(judge, rows)["excluded"]
    assert [e["reason"] for e in excluded] == ["Protocolo de extracción distinto"]


def _ranked_study(tmp_path):
    """Train the judge on a synthetic study and return it with feature rows for its runs."""
    study = voted_study(tmp_path)
    for story in study.export()["stories"]:
        extract_features(
            story["text"],
            SyntheticProvider(),
            model="fake",
            output=tmp_path / "features" / f"{story['id']}.json",
        )
    judge = train_judge(study.export(), load_study_features(study))
    extractions = study_extractions(tmp_path / "study.sqlite3")
    rows = [
        read_features(p.parent, extractions=extractions)
        for p in sorted((tmp_path / "runs").rglob("story.md"))
    ]
    return judge, rows


def test_training_stories_stay_ranked_and_marked_but_leave_the_top_ten(tmp_path):
    judge, rows = _ranked_study(tmp_path)
    head = rank_features(judge, rows)["combined_auxiliary"][0]["story"]
    hashes = {r["story"]: r["text_hash"] for r in rows}
    report = rank_features(judge, rows, training={hashes[head]})
    combined = [r["story"] for r in report["combined_auxiliary"]]
    assert combined[0] == head and report["combined_auxiliary"][0]["marks"][0] == "training"
    assert all(head in [r["story"] for r in ranking] for ranking in report["rankings"].values())
    assert [t["story"] for t in report["top_ten"]] == combined[1:]
    assert all(not t["strengths"] and not t["weaknesses"] for t in report["top_ten"])
    words = {r["story"]: r["features"]["T01"]["value"] for r in rows}
    length = report["length_control"]
    assert [r["story"] for r in length] == sorted(words, key=lambda s: (-words[s], s))
    assert all(
        s["positions"]["length"] == [r["story"] for r in length].index(s["story"]) + 1
        for s in report["stories"]
    )
    t01 = report["top_ten_profile"]["T01"]
    assert t01["corpus"] == {"median": statistics.median(words.values()), "n": 6}
    assert (t01["top_ten"]["n"], t01["rest"]) == (5, {"median": words[head], "n": 1})
    sheet = top_ten_sheet(report, tmp_path)
    assert [line for line in sheet.splitlines() if "(Josue)" in line] == [
        "- Fortalezas (Josue):",
        "- Debilidades (Josue):",
    ] * 5
    assert "no generaliza" in sheet and "Sin `--study`" not in sheet


@pytest.mark.parametrize(
    ("pipeline", "work", "marks"),
    [
        ("7.0", "01", ["version-no-comparable"]),
        ("7.1", "03", ["version-no-comparable"]),
        ("7.10", "03", []),
        ("7.22", "04", ["premisa-no-vista"]),
        ("7.22", None, ["premisa-no-vista"]),
    ],
)
def test_marks_compare_versions_exactly_and_premises_with_the_pilot_works(pipeline, work, marks):
    row = {"text_hash": "h", "pipeline_version": pipeline, "work": work}
    assert story_marks(row, None) == marks
    assert story_marks(row, {"h"}) == ["training", *marks]


def test_prompt_work_matches_any_profile_variant_of_the_catalog():
    blocks = re.findall(
        r"<!-- PROMPT_(\w+?)_START -->\s*(.*?)\s*<!--", resource_text("prompts.md"), re.S
    )
    for marker, text in blocks:
        assert prompt_work("  " + text.replace(" ", "\n ", 3)) == marker[:2]
    assert prompt_work("Una historia que no está en el catálogo.") is None
    assert prompt_work(None) is None


def test_rank_command_writes_sheet_with_horizontal_link_and_warns_without_study(
    tmp_path, monkeypatch
):
    judge, rows = _ranked_study(tmp_path)
    for row in rows:
        report = next(
            r
            for r in study_extractions(tmp_path / "study.sqlite3").values()
            if r["identity"]["text_hash"] == row["text_hash"]
        )
        Path(row["story"], "features").mkdir()
        Path(row["story"], "features", "features.json").write_text(
            json.dumps(report), encoding="utf-8"
        )
    manifest = tmp_path / "Evaluations" / "horizontal" / "manifiesto-matriz.json"
    manifest.parent.mkdir(parents=True)
    unit = {"run": "Stories/Stagecraft/synthetic-03", "estado": "completed"}
    manifest.write_text(json.dumps({"units": {"M01/03/r1": unit}}), encoding="utf-8")
    judge_path, output = tmp_path / "judge.json", tmp_path / "ranking" / "ranking.json"
    judge_path.write_text(json.dumps(judge), encoding="utf-8")
    runs = str(tmp_path / "runs")
    assert learning_cli.rank_main([str(judge_path), runs, "--output", str(output)]) == 0
    report = json.loads(output.read_text(encoding="utf-8"))
    assert not report["training_marked"] and len(report["top_ten"]) == 6
    linked = next(t for t in report["top_ten"] if t["run_id"] == "synthetic-03")
    assert [h["unit"] for h in linked["horizontal"]] == ["M01/03/r1"]
    assert all(t["marks"] == ["premisa-no-vista"] for t in report["top_ten"])
    sheet = output.with_suffix(".md").read_text(encoding="utf-8")
    assert "[M01/03/r1](../Evaluations/horizontal/manifiesto-matriz.json)" in sheet
    assert "Sin `--study`" in sheet

    def other_drive(*_):
        raise ValueError("path is on mount 'E:', start on mount 'C:'")

    monkeypatch.setattr(learning_cli.os.path, "relpath", other_drive)
    assert f"]({manifest.resolve().as_posix()})" in top_ten_sheet(report, output.parent)


CHAPTERS = "# Título\n\nAntes.\n\n## Uno\n\nA1.\n\nA2.\n\n## Dos\n\nB1.\n"
THIRDS = "# Base\n\n" + "\n\n".join(f"P{i}." for i in range(7)) + "\n"


@pytest.mark.parametrize("text", [CHAPTERS, THIRDS])
def test_perturbations_are_deterministic_shuffles_and_strict_prefixes(text):
    first, order = shuffled(text, seed=3, story="s1")
    assert (first, order) == shuffled(text, seed=3, story="s1")
    assert order != sorted(order) and first.splitlines()[0] == text.splitlines()[0]
    assert sorted(b for _, b in blocks(first)) == sorted(b for _, b in blocks(text))
    cut, removed = no_ending(text)
    assert removed >= 1 and len(cut) < len(text) and text.startswith(cut.rstrip())
    assert not blocks(cut)[-1][1].startswith("#")


def test_perturb_command_builds_cases_only_from_matching_extractions(tmp_path):
    study = voted_study(tmp_path)
    provider = SyntheticProvider()
    for story in study.export()["stories"]:
        extract_features(
            story["text"],
            provider,
            model="fake",
            output=tmp_path / "features" / f"{story['id']}.json",
        )
    db, out, cases = tmp_path / "study.sqlite3", tmp_path / "perturbed", tmp_path / "casos.json"
    assert perturb_main([str(db), "--out", str(out)]) == 0
    first = sorted(p.read_bytes() for p in out.rglob("story.md"))
    assert perturb_main([str(db), "--out", str(out)]) == 0
    assert sorted(p.read_bytes() for p in out.rglob("story.md")) == first and len(first) == 12
    for path in out.rglob("story.md"):
        text = path.read_text(encoding="utf-8")
        extract_features(
            text, provider, model="fake", output=path.parent / "features" / "features.json"
        )
    stale = next(out.glob("*-no-ending"))
    (stale / "story.md").write_text("Otro texto.", encoding="utf-8")
    assert perturb_main([str(db), "--out", str(out), "--casos", str(cases)]) == 1
    built = json.loads(cases.read_text(encoding="utf-8"))
    assert len(built) == 11 and stale.name not in {c["name"] for c in built}
    judge = train_judge(study.export(), load_study_features(study))
    report = perturbation_report(judge, built)
    assert {r["name"] for r in report} == {c["name"] for c in built}
