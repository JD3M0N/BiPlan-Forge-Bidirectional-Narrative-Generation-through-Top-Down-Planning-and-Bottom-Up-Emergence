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
