import csv
import json
from pathlib import Path

import pytest
from asg_evaluation import results

HISTORIES = {"H1": "sa", "H2": "sb"}


def validation(accuracy: float, tested: int) -> dict:
    return {"accuracy": accuracy, "tested_votes": tested, "chance_accuracy": 0.5}


def positions(first: int, second: int, third: int, combined: int, length: int) -> dict:
    return {"H01": first, "H02": second, "H03": third, "combined": combined, "length": length}


def write(path: Path, document) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document), encoding="utf-8")


@pytest.fixture
def evaluations(tmp_path: Path) -> Path:
    root = tmp_path / "Evaluations"
    pilot = root / "estudio-piloto-722"
    criteria = {
        key: {
            "validation": validation(0.4, 20),
            "family_validation": validation(0.5, 20),
            "length_baseline": {"by_story": validation(0.6, 20), "by_family": validation(0.7, 20)},
        }
        for key in ("H01", "H02", "H03")
    }
    deltas = {"H01": -0.8, "H02": 1.594, "H03": 0.2}
    case = {key: {"delta": value, "decreased": value < 0} for key, value in deltas.items()}
    write(
        pilot / "juez.json",
        {
            "criteria": criteria,
            "perturbations": [
                {"name": "sa-shuffled", "criteria": case},
                {"name": "sb-no-ending", "criteria": case},
            ],
        },
    )
    write(pilot / "protocolo.json", {"historias": HISTORIES})
    entry = {
        "status": "insufficient",
        "components": [["sa"], ["sb"]],
        "agreement": {"agreement": 0.4, "krippendorff_alpha_nominal": -0.14, "abstentions": 3},
    }
    write(
        pilot / "preferencias.json",
        {
            group: {key: entry for key in ("H01", "H02", "H03")}
            for group in ("all", "without_author")
        },
    )
    story = {"format": "simulated", "marks": [], "positions": positions(1, 2, 3, 4, 5)}
    trained = {"format": "baseline", "marks": ["training"], "positions": positions(3, 1, 2, 1, 4)}
    write(
        root / "ranking" / "ranking-2026-11-03.json",
        {
            "stories": [
                {**trained, "story": "Stories\\Baseline\\01-fantasia-canonica-2"},
                {**story, "story": "Stories\\Stagecraft\\20261030-130819-el-misterio-del-faro"},
            ],
            "excluded": [
                {"story": "a", "reason": "Extracción incompleta"},
                {"story": "b", "reason": "Extracción incompleta"},
                {"story": "c", "reason": "Run no completado"},
            ],
            "top_ten": [{"story": "Stories\\Stagecraft\\20261030-130819-el-misterio-del-faro"}],
            "top_ten_profile": {
                "T01": {
                    "top_ten": {"median": 1403.0, "n": 1},
                    "rest": {"median": 978.0, "n": 1},
                    "corpus": {"median": 1190.25, "n": 2},
                },
                "T08": {
                    "top_ten": {"median": 0.0599, "n": 1},
                    "rest": {"median": None, "n": 0},
                    "corpus": {"median": 0.0599, "n": 1},
                },
            },
        },
    )
    horizontal = root / "horizontal"
    write(
        horizontal / "manifiesto-matriz.json",
        {
            "units": {
                "M01/01/r1": {"estado": "completed"},
                "M01/04/r2": {"estado": "failed"},
                "M03/01/r1": {"estado": "completed"},
                "M03/01/r2": {"estado": "pendiente"},
            }
        },
    )
    csv_path = horizontal / "piloto-03" / "horizontal.csv"
    csv_path.parent.mkdir(parents=True)
    rows = [
        ("M01", "base", "T01", "1560", ""),
        ("M01", "base", "T06", "0.4048", ""),
        ("M03", "pares", "T01", "-176.0", "n insuficiente"),
        ("M03", "pares", "T06", "0.06", "n insuficiente"),
        ("M03", "pares", "T08", "-0.04", "n insuficiente"),
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["pipeline_version", "celda", "tipo", "rasgo", "mediana", "lectura"])
        writer.writerows(
            ("7.22", cell, kind, trait, median, read) for cell, kind, trait, median, read in rows
        )
    return root


def run(evaluations: Path, out: Path, *extra: str) -> int:
    return results.main(
        [
            *("--evaluations", str(evaluations)),
            *("--tablas", str(out)),
            *("--figuras", str(out.parent / "figuras")),
            *("--fecha", "2026-11-03"),
            *extra,
        ]
    )


def test_tables_show_the_stored_values(evaluations, tmp_path, capsys):
    out = tmp_path / "tablas"
    assert run(evaluations, out) == 0
    assert json.loads(capsys.readouterr().out) == {"generadas": 9, "no_disponibles": []}
    judge = (out / "juez.tex").read_text(encoding="utf-8")
    assert "Creatividad (H01) & 20 & 0,40 (8) & 0,50 (10) & 0,60 (12) & 0,70 (14) & 0,5" in judge
    prefs = (out / "preferencias.tex").read_text(encoding="utf-8")
    assert "insuficiente & 2 & 0,40 & $-$0,14 & 3" in prefs
    assert "sin autor" in prefs
    perturbations = (out / "perturbaciones.tex").read_text(encoding="utf-8")
    assert "H1 barajada & $-$0,80 & $+$1,59 & $+$0,20" in perturbations
    assert "H2 sin desenlace" in perturbations
    assert "Bajan (de 2) & 2 & 0 & 0" in perturbations
    pilot = (out / "piloto.tex").read_text(encoding="utf-8")
    assert "Base (valores absolutos) & 1.560 & 0,40 & --- & ---" in pilot
    assert "Narrativa desde el plan & $-$176 & $+$0,06 & $-$0,04 & n insuficiente" in pilot
    matrix = (out / "matriz.tex").read_text(encoding="utf-8")
    assert "M01 Base simulada & 2 & 1 & 1 & 0" in matrix
    assert "Total & 4 & 2 & 1 & 1" in matrix


def test_ranking_tables_and_judge_figure(evaluations, tmp_path):
    out = tmp_path / "tablas"
    run(evaluations, out)
    coverage = (out / "ranking_cobertura.tex").read_text(encoding="utf-8")
    assert "Ordenada & Ordenadas por el juez & 2" in coverage
    assert "Ordenada & de ellas, del entrenamiento (fuera de las diez) & 1" in coverage
    assert "Ordenada & Las diez primeras (las que haya) & 1" in coverage
    assert "Elegible que sale & Extracción incompleta & 2" in coverage
    assert coverage.index("Extracción incompleta") < coverage.index(
        "No elegible & Run no completado & 1"
    )
    places = (out / "ranking_puestos.tex").read_text(encoding="utf-8")
    assert "20261030-130819-el-misterio-del-faro & simulado & --- & 1 & 2 & 3 & 4 & 5" in places
    assert places.index("01-fantasia-canonica-2") < places.index("20261030-130819")
    assert "línea base & entrenamiento & 3 & 1 & 2 & 1 & 4" in places
    profile = (out / "ranking_perfil.tex").read_text(encoding="utf-8")
    assert "T01 & Palabras & 1.403 (1) & 978 (1) & 1.190 (2)" in profile
    assert "T08 & Repetición de trigramas & 0,060 (1) & --- & 0,060 (1)" in profile
    figure = (tmp_path / "figuras" / "juez.tex").read_text(encoding="utf-8")
    assert figure.startswith("\\begin{tikzpicture}") and "\\end{tikzpicture}" in figure
    assert "rectangle (0.4000," in figure and "{azar}" in figure


def test_manifest_hashes_inputs_and_outputs_and_reruns_identically(evaluations, tmp_path):
    out = tmp_path / "tablas"
    run(evaluations, out)
    first = {path.name: path.read_bytes() for path in out.iterdir()}
    manifest = json.loads(first["manifiesto.json"])
    assert manifest["fecha"] == "2026-11-03" and manifest["comando"] == "asg-results"
    entry = manifest["tablas"]["juez"]
    assert entry["estado"] == "generada"
    assert entry["entradas"]["estudio-piloto-722/juez.json"] == results.sha256(
        evaluations / "estudio-piloto-722" / "juez.json"
    )
    assert entry["salidas"]["juez.tex"] == results.sha256(out / "juez.tex")
    assert "tab:coste" in manifest["a_mano"]
    run(evaluations, out)
    assert {path.name: path.read_bytes() for path in out.iterdir()} == first


def test_missing_input_marks_that_table_and_keeps_the_rest(evaluations, tmp_path, capsys):
    (evaluations / "horizontal" / "piloto-03" / "horizontal.csv").unlink()
    out = tmp_path / "tablas"
    assert run(evaluations, out) == 1
    assert json.loads(capsys.readouterr().out)["no_disponibles"] == ["piloto"]
    assert results.UNAVAILABLE in (out / "piloto.tex").read_text(encoding="utf-8")
    assert "horizontal.csv" in (out / "piloto.tex").read_text(encoding="utf-8")
    manifest = json.loads((out / "manifiesto.json").read_text(encoding="utf-8"))
    assert manifest["tablas"]["piloto"]["estado"] == "no disponible"
    assert manifest["tablas"]["piloto"]["entradas"]["horizontal/piloto-03/horizontal.csv"] is None
    assert manifest["tablas"]["juez"]["estado"] == "generada"


@pytest.mark.parametrize(
    ("value", "decimals", "signed", "expected"),
    [
        (1560, 0, False, "1.560"),
        (0.4048, 2, False, "0,40"),
        (-176.0, 0, True, "$-$176"),
        (0.06, 2, True, "$+$0,06"),
        (-0.14, 2, False, "$-$0,14"),
        (None, 2, True, "---"),
    ],
)
def test_number_uses_spanish_separators_and_math_signs(value, decimals, signed, expected):
    assert results.number(value, decimals, signed=signed) == expected


def test_ranking_defaults_to_the_newest_file_and_can_be_chosen(evaluations, tmp_path):
    older = evaluations / "ranking" / "ranking-2026-10-01.json"
    older.write_text("{}", encoding="utf-8")
    assert results.latest_ranking(evaluations) == "ranking/ranking-2026-11-03.json"
    out = tmp_path / "tablas"
    assert run(evaluations, out, "--ranking", "ranking/ranking-2026-10-01.json") == 0
    manifest = json.loads((out / "manifiesto.json").read_text(encoding="utf-8"))
    assert "ranking/ranking-2026-10-01.json" in manifest["tablas"]["ranking_puestos"]["entradas"]
    older.unlink()
    (evaluations / "ranking" / "ranking-2026-11-03.json").unlink()
    assert results.latest_ranking(evaluations) == results.RANKING_GLOB
    assert run(evaluations, out) == 1
