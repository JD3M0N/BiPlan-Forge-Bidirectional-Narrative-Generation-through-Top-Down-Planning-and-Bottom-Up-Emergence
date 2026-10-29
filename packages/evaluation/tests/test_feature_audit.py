"""Review sheet, test-retest summary and verdict aggregation for the extractor audit."""

import csv

import pytest
from asg_evaluation.catalog import core_ids, digest
from asg_evaluation.feature_audit import (
    SHEET_COLUMNS,
    main,
    retest_summary,
    review_sheet,
    spearman,
    verdict_summary,
    write_sheet,
)
from asg_evaluation.features import measurement

TEXT = "Ada tenía la llave.\n\nAda nunca tuvo la llave.\n\nBea mintió a Ada."


def occurrence(paragraph, quote, label="e"):
    return {
        "scene": 0,
        "label": label,
        "explanation": "motivo",
        "evidence": [{"paragraph": paragraph, "text": quote, "start": 0, "end": 1}],
    }


def extraction(features, text=TEXT):
    return {"identity": {"text_hash": digest(text)}, "features": features}


def unlogged_core():
    from asg_evaluation.catalog import catalog

    rows = catalog()
    return next(k for k in core_ids() if k[0] == "R" and not rows[k]["validable_contra"])


def test_sheet_has_a_row_per_occurrence_and_one_for_hollow_features():
    keys = [k for k in core_ids() if k[0] == "R"][:3]
    cited, zero, na = keys
    features = {
        cited: measurement(2, evidence=[occurrence(0, "la llave"), occurrence(1, "nunca tuvo")]),
        zero: measurement(0),
        na: measurement(status="not_applicable", reason="no hay ocurrencias posibles"),
        "T01": measurement(14),
        "X03": measurement(0.5),
    }
    rows = review_sheet(extraction(features), TEXT)
    by_key = {k: [r for r in rows if r["rasgo"] == k] for k in keys}
    assert len(by_key[cited]) == 2 and len(by_key[zero]) == 1 and len(by_key[na]) == 1
    assert "Ada nunca tuvo la llave." in by_key[cited][1]["parrafo"]
    assert by_key[cited][1]["cita"] == "[¶1] nunca tuvo"
    assert by_key[na][0]["notas"] == "no hay ocurrencias posibles"
    assert by_key[zero][0]["ocurrencia"] == ""
    assert not {"T01", "X03"} & {r["rasgo"] for r in rows}  # computed by code, not reviewed


def test_partial_scope_keeps_unlogged_core_and_hollow_features_only():
    unlogged = unlogged_core()
    from asg_evaluation.catalog import catalog

    rows = catalog()
    logged = next(
        k for k in core_ids() if k[0] in "RX" and rows[k]["validable_contra"] and k != "X03"
    )
    features = {
        unlogged: measurement(1, evidence=[occurrence(0, "Ada")]),
        logged: measurement(1, evidence=[occurrence(0, "Ada")]),
    }
    partial = {r["rasgo"] for r in review_sheet(extraction(features), TEXT, "parcial")}
    assert partial == {unlogged}
    features[logged] = measurement(0)
    partial = {r["rasgo"] for r in review_sheet(extraction(features), TEXT, "parcial")}
    assert partial == {unlogged, logged}
    assert {r["rasgo"] for r in review_sheet(extraction(features), TEXT)} == {unlogged, logged}


def test_sheet_rejects_foreign_text_and_misplaced_quotes():
    key = unlogged_core()
    good = extraction({key: measurement(1, evidence=[occurrence(0, "Ada")])})
    with pytest.raises(ValueError, match="no corresponde"):
        review_sheet(good, TEXT + " más")
    bad = extraction({key: measurement(1, evidence=[occurrence(0, "Bea")])})
    with pytest.raises(ValueError, match="no está en el texto"):
        review_sheet(bad, TEXT)
    with pytest.raises(ValueError, match="alcance"):
        review_sheet(good, TEXT, "otro")


def test_retest_summary_agreement_difference_rank_and_state_changes():
    key = "R02"
    pairs = []
    for a, b in [(4, 4), (2, 3), (8, 6), (0, 0)]:
        pairs.append(
            (
                extraction({key: measurement(a), "R04": measurement(a)}),
                extraction({key: measurement(b), "R04": measurement(status="failed")}),
            )
        )
    row = retest_summary(pairs)[key]
    assert row["measured_in_both"] == 4 and row["exact_agreement"] == 0.5
    assert row["mean_relative_difference"] == pytest.approx((0 + 1 / 3 + 0.25 + 0) / 4)
    assert row["rank_correlation"] == pytest.approx(1.0)
    assert row["state_changes"] == 0 and row["meets_threshold"]
    unstable = retest_summary(pairs)["R04"]
    assert unstable["state_changes"] == 4 and not unstable["meets_threshold"]
    assert unstable["measured_in_both"] == 0 and unstable["exact_agreement"] is None


def test_spearman_handles_ties_short_series_and_constants():
    assert spearman([1, 2, 3, 4], [10, 20, 30, 40]) == pytest.approx(1.0)
    assert spearman([1, 2, 3], [3, 2, 1]) == pytest.approx(-1.0)
    assert spearman([1, 2], [1, 2]) is None
    assert spearman([1, 1, 1], [1, 2, 3]) is None


def test_verdict_summary_precision_coverage_and_insufficient_evidence(tmp_path):
    key = unlogged_core()
    features = {
        key: measurement(6, evidence=[occurrence(i % 3, "Ada") for i in range(6)]),
        "R04": measurement(0),
    }
    sheet = tmp_path / "hoja.csv"
    write_sheet(review_sheet(extraction(features), TEXT), sheet)
    with open(sheet, encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert list(rows[0]) == list(SHEET_COLUMNS)
    verdicts = ["Correcto"] * 4 + ["incorrecto", "dudoso"]
    filled = []
    for row in rows:
        if row["rasgo"] == key:
            row["veredicto"] = verdicts.pop(0)
        elif row["rasgo"] == "R04":
            row["ocurrencias_omitidas"] = "2"
        filled.append(row)
    filled[0]["ocurrencias_omitidas"] = "1"
    done = tmp_path / "hecha.csv"
    with open(done, "w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SHEET_COLUMNS)
        writer.writeheader()
        writer.writerows(filled)
    summary = verdict_summary([done])
    assert summary[key] == {
        "correct": 4,
        "incorrect": 1,
        "doubtful": 1,
        "omitted": 1,
        "judged": 5,
        "precision": 0.8,
        "coverage": 0.8,
        "insufficient_evidence": False,
    }
    assert summary["R04"]["omitted"] == 2 and summary["R04"]["precision"] is None
    assert summary["R04"]["insufficient_evidence"]
    filled[0]["veredicto"] = "quizá"
    with open(done, "w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SHEET_COLUMNS)
        writer.writeheader()
        writer.writerows(filled)
    with pytest.raises(ValueError, match="veredicto desconocido"):
        verdict_summary([done])


def test_cli_writes_sheet_summary_and_verdicts(tmp_path):
    from asg_core import atomic_write_json

    key = unlogged_core()
    first = extraction({key: measurement(1, evidence=[occurrence(0, "Ada")])})
    second = extraction({key: measurement(1, evidence=[occurrence(0, "Ada")])})
    (tmp_path / "story.md").write_text(TEXT, encoding="utf-8")
    atomic_write_json(tmp_path / "a.json", first)
    atomic_write_json(tmp_path / "b.json", second)
    out = tmp_path / "out.json"
    sheet = tmp_path / "hoja.csv"
    args = [str(tmp_path / "a.json"), "--texto", str(tmp_path / "story.md")]
    args += ["--hoja", str(sheet), "--alcance", "parcial", "--output", str(out)]
    args += ["--pares", str(tmp_path / "a.json"), str(tmp_path / "b.json")]
    args += ["--veredictos", str(sheet)]
    assert main(args) == 0 and sheet.is_file()
    import json

    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["retest_summary"][key]["state_changes"] == 0
    assert report["verdicts"][key]["judged"] == 0
    with pytest.raises(SystemExit):
        main([str(tmp_path / "a.json"), "--hoja", str(sheet), "--output", str(out)])
    with pytest.raises(SystemExit):
        main(["--pares", str(tmp_path / "a.json"), "--output", str(out)])
