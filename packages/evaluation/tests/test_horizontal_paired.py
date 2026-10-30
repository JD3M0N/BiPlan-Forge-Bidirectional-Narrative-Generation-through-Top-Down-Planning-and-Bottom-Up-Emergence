"""The paired horizontal report compares each derived run with its source plan."""

import json

import pytest
from asg_evaluation.feature_cli import main
from asg_evaluation.feature_report import horizontal_report, read_features
from asg_evaluation.horizontal_paired import NOT_MEASURED, _reading, paired_report, paired_rows
from evaluation_fakes import synthetic_run


def _run(root, name, number, *, generator="7.22.0", source=None, pipeline="7.22"):
    """A synthetic run with a generator version and, optionally, a recorded source run."""
    run = synthetic_run(root / name, number)
    (run / "generator_version.json").write_text(
        json.dumps({"generator_version": generator, "pipeline_version": pipeline}),
        encoding="utf-8",
    )
    meta = json.loads((run / "metadata.json").read_text(encoding="utf-8"))
    (run / "metadata.json").write_text(
        json.dumps(meta | {"pipeline_version": pipeline}), encoding="utf-8"
    )
    if source:
        (run / "source_run.json").write_text(json.dumps({"run_id": source}), encoding="utf-8")
    return run


def _entry(cell, run, *, source=None, work="01", kind="simulated"):
    """A completed manifest unit."""
    return {
        "celda": cell,
        "obra": work,
        "repeticion": 1,
        "tipo": kind,
        "fuente": source,
        "modo_fuente": "narrate" if source else None,
        "estado": "completed",
        "run": f"Stories/{run}",
        "fallidos": [],
    }


@pytest.fixture
def fixture(tmp_path):
    """One source and two derived runs from different 7.22 patches."""
    _run(tmp_path, "base", 1, generator="7.22.0")
    _run(tmp_path, "d1", 3, generator="7.22.0", source="base")
    _run(tmp_path, "d2", 5, generator="7.22.1", source="base")
    manifest = {
        "units": {
            "M01/01-r1": _entry("M01", "base"),
            "M04/01-r1": _entry("M04", "d1", source="M01/01-r1"),
            "M05/01-r1": _entry("M05", "d2", source="M01/01-r1"),
        }
    }
    rows = [read_features(tmp_path / name) for name in ("base", "d1", "d2")]
    return tmp_path, rows, manifest


def _cell(report, name):
    """Return one cell of the single pipeline group."""
    (group,) = report["groups"]
    return next(cell for cell in group["cells"] if cell["celda"] == name)


def _feature(cell, key):
    """Return one feature record of a cell."""
    return next(f for f in cell["features"] if f["id"] == key)


def test_pairs_share_one_pipeline_group_and_report_differences(fixture):
    _, rows, manifest = fixture
    report = paired_report(rows, manifest, {"M04": ("tono", "sombrío")})
    (group,) = report["groups"]
    assert group["pipeline_version"] == "7.22"
    assert group["generator_versions"] == ["7.22.0", "7.22.1"]
    base = _feature(_cell(report, "M01"), "T01")["mediana"]
    words = {r["run_id"]: r["features"]["T01"]["value"] for r in rows}
    cell = _cell(report, "M04")
    assert (cell["eje"], cell["nivel"], cell["tipo"]) == ("tono", "sombrío", "pares")
    t01 = _feature(cell, "T01")
    assert t01["n"] == 1
    assert t01["mediana"] == words["d1"] - words["base"] == words["d1"] - base
    assert t01["lectura"] == "n insuficiente"
    assert _feature(_cell(report, "M05"), "T01")["mediana"] == words["d2"] - words["base"]
    assert report["descartadas"] == []


def test_unmeasured_feature_is_not_zero_and_core_comes_first(fixture):
    _, rows, manifest = fixture
    report = paired_report(rows, manifest)
    cell = _cell(report, "M04")
    r01 = _feature(cell, "R01")
    assert (r01["n"], r01["mediana"], r01["lectura"]) == (0, None, NOT_MEASURED)
    ids = [f["id"] for f in cell["features"]]
    flags = [f["nucleo"] for f in cell["features"]]
    assert flags == sorted(flags, reverse=True)
    assert ids.index("T01") < ids.index("P09") < ids.index("K01")
    assert paired_rows(report)[0][5] == ids[0]


def test_pair_with_wrong_source_is_discarded_with_reason(fixture):
    tmp_path, rows, manifest = fixture
    (tmp_path / "d1" / "source_run.json").write_text(json.dumps({"run_id": "otra"}))
    rows = [read_features(tmp_path / name) for name in ("base", "d1", "d2")]
    report = paired_report(rows, manifest)
    assert report["descartadas"] == [
        {"unidad": "M04/01-r1", "motivo": "C18 no coincide con la fuente del manifiesto"}
    ]
    assert all(cell["celda"] != "M04" for cell in report["groups"][0]["cells"])


@pytest.mark.parametrize(
    ("diffs", "noise", "expected"),
    [
        ([5, 6, 7, 8, 9, 10], {"valor": 2, "obras": 3}, "interpretable"),
        ([5, 6, 7, 8, 9, -1], {"valor": 2, "obras": 3}, "interpretable"),
        ([5, 6, 7, -8, -9, 10], {"valor": 2, "obras": 3}, "dentro del ruido"),
        ([1, 1, 1, 1, 1, 1], {"valor": 2, "obras": 3}, "dentro del ruido"),
        ([5, 6, 7, 8, 9, 10], None, "sin ruido medido"),
        ([5, 6, 7], {"valor": 2, "obras": 3}, "n insuficiente"),
    ],
)
def test_noise_rule_needs_size_and_five_of_six_signs(diffs, noise, expected):
    assert _reading(diffs, noise) == expected


def test_cli_with_manifest_writes_json_and_csv_and_axis_is_unchanged(fixture, capsys):
    tmp_path, rows, manifest = fixture
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    out = tmp_path / "out" / "horizontal.json"
    assert main([str(tmp_path), "--horizontal", str(out), "--manifest", str(path)]) == 0
    assert json.loads(out.read_text(encoding="utf-8"))["paired"] is True
    assert out.with_suffix(".csv").read_text(encoding="utf-8").startswith("pipeline_version,")
    plain = tmp_path / "plain.json"
    assert main([str(tmp_path), "--horizontal", str(plain)]) == 0
    assert json.loads(plain.read_text(encoding="utf-8")) == json.loads(
        json.dumps(horizontal_report(rows, "C02"))
    )
    capsys.readouterr()
