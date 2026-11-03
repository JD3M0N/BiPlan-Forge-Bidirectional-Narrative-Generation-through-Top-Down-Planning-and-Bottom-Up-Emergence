"""The pairwise study: phases, lazy blind assignment, reading before voting, private export."""

import json
import sqlite3
from collections import Counter

import pytest
from asg_evaluation.study import QUESTIONS_PER_READER, StudyRepository
from evaluation_fakes import synthetic_run, voted_study


def test_phases_reading_recognition_and_votes(tmp_path):
    study = StudyRepository(tmp_path / "study.sqlite3")
    runs = [synthetic_run(tmp_path / f"run-{i}", i) for i in range(4)]
    alice = study.participant("111")
    own = study.add_story(runs[0], owner=alice)
    assert study.add_story(runs[0], owner=alice) == own  # idempotent by run
    for run in runs[1:3]:
        study.add_story(run)
    with pytest.raises(ValueError, match="no está abierta"):
        study.next_question(alice)
    study.exclude(study.add_story(runs[3]))
    study.open()
    with pytest.raises(ValueError, match="recogida"):
        study.add_story(synthetic_run(tmp_path / "late", 9))

    question = study.next_question(alice)
    shown = {question["left"]["id"], question["right"]["id"]}
    assert own not in shown and len(shown) == 2 and question["criterion"] == "H01"
    with pytest.raises(ValueError, match="lectura"):
        study.vote(alice, question["id"], "A")
    study.recognize(alice, question["id"], question["left"]["id"])
    # Alice owns one story and knows another: only one story is left, so no pair remains.
    assert study.next_question(alice) is None

    bob = study.participant("222")
    question = study.next_question(bob)
    assert study.next_question(bob)["id"] == question["id"]  # the open question is kept
    for side in ("left", "right"):
        study.mark_read(bob, question["id"], question[side]["id"])
    assert study.vote(bob, question["id"], "abstain") is True
    assert study.vote(bob, question["id"], "A") is False
    following = study.next_question(bob)
    assert following["left"]["read"] or following["right"]["read"]  # reuses what was read
    study.close()
    with pytest.raises(ValueError):
        study.next_question(bob)


def test_assignment_is_capped_connected_and_export_is_pseudonymous(tmp_path):
    study = voted_study(tmp_path)
    data = study.export()
    readers = Counter(v["participant"] for v in data["votes"])
    assert set(readers.values()) == {QUESTIONS_PER_READER}
    for reader in readers:
        mine = [v for v in data["votes"] if v["participant"] == reader]
        asked = [(v["criterion"], frozenset((v["left"], v["right"]))) for v in mine]
        assert len(set(asked)) == len(asked)
        assert Counter(v["criterion"] for v in mine) == {"H01": 5, "H02": 5, "H03": 5}
        owned = {s["id"] for s in data["stories"] if s["owner"] == reader}
        assert not owned & {s for v in mine for s in (v["left"], v["right"])}
    assert all(len(c["components"]) == 1 for c in data["coverage"].values())
    text = json.dumps(data, ensure_ascii=False)
    assert "run_path" not in text and "synthetic-00" not in text  # no local paths
    assert all(set(p) == {"id", "is_author"} for p in data["participants"])
    assert [p["is_author"] for p in data["participants"]].count(1) == 1
    legacy = tmp_path / "old.sqlite3"
    with sqlite3.connect(legacy) as db:
        db.execute("PRAGMA user_version=4")
    with pytest.raises(ValueError, match="esquema"):
        StudyRepository(legacy)


def _sheet_study(tmp_path):
    """Open a study of three stories and return it with its sheet codes."""
    study = StudyRepository(tmp_path / "study.sqlite3")
    ids = [study.add_story(synthetic_run(tmp_path / f"run-{i}", i)) for i in range(3)]
    study.open()
    return study, dict(zip(("H1", "H2", "H3"), ids, strict=True))


def _sheet_row(reader, question, criterion, a, b, choice):
    return {
        "lector": reader,
        "pregunta": str(question),
        "criterio": criterion,
        "historia_a": a,
        "historia_b": b,
        "eleccion": choice,
        "fuente": "papel",
    }


def test_import_votes_keeps_transcribed_order_and_null_seconds(tmp_path):
    study, codes = _sheet_study(tmp_path)
    rows = [
        _sheet_row("L1", 1, "creatividad", "H1", "H3", "A"),
        _sheet_row("L1", 2, "personajes", "H1", "H3", "abstencion"),
        _sheet_row("L2", 1, "trama", "H3", "H2", "B"),
    ]
    assert study.import_votes(rows, codes) == {"votes": 3, "readers": 2}
    data = study.export()
    assert Counter(v["choice"] for v in data["votes"]) == Counter(A=1, B=1, abstain=1)
    assert all(v["seconds"] is None for v in data["votes"])
    first = next(v for v in data["votes"] if v["choice"] == "A")
    assert (first["left"], first["right"], first["criterion"]) == (codes["H1"], codes["H3"], "H01")
    assert len(data["participants"]) == 2 and len(data["readings"]) == 4


@pytest.mark.parametrize(
    ("bad", "message"),
    [
        (_sheet_row("L1", 3, "creatividad", "H1", "H3", "A"), "ya votó ese par"),
        (_sheet_row("L1", 1, "trama", "H1", "H2", "A"), "ya tiene la pregunta"),
        (_sheet_row("L1", 3, "trama", "H1", "H9", "A"), "historia desconocida"),
        (_sheet_row("L1", 3, "trama", "H2", "H2", "A"), "la misma"),
        (_sheet_row("L1", 3, "estilo", "H1", "H2", "A"), "criterio desconocido"),
        (_sheet_row("L1", 3, "trama", "H1", "H2", ""), "elección desconocida"),
    ],
)
def test_import_votes_rejects_bad_rows_without_writing(tmp_path, bad, message):
    study, codes = _sheet_study(tmp_path)
    rows = [_sheet_row("L1", 1, "creatividad", "H1", "H3", "A"), bad]
    rows.insert(1, _sheet_row("L1", 2, "trama", "H2", "H3", "B"))
    with pytest.raises(ValueError, match=message):
        study.import_votes(rows, codes)
    assert study.export()["votes"] == [] and study.export()["participants"] == []


def test_import_votes_caps_questions_per_reader(tmp_path):
    study = StudyRepository(tmp_path / "study.sqlite3")
    ids = [study.add_story(synthetic_run(tmp_path / f"run-{i}", i)) for i in range(6)]
    study.open()
    codes = {f"H{i + 1}": sid for i, sid in enumerate(ids)}
    pairs = [(f"H{a}", f"H{b}") for a in range(1, 7) for b in range(a + 1, 7)]
    rows = [_sheet_row("L1", n, "trama", a, b, "A") for n, (a, b) in enumerate(pairs, start=1)]
    assert study.import_votes(rows, codes)["votes"] == QUESTIONS_PER_READER
    with pytest.raises(ValueError, match="no se reimporta"):
        study.import_votes(rows, codes)
    fresh = [_sheet_row("L3", n, "trama", a, b, "A") for n, (a, b) in enumerate(pairs, 1)]
    fresh.append(_sheet_row("L3", 16, "creatividad", "H1", "H2", "A"))
    with pytest.raises(ValueError, match="máximo"):
        study.import_votes(fresh, codes)
    assert len(study.export()["votes"]) == QUESTIONS_PER_READER
