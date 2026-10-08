"""Durable blind assignments, lifecycle restrictions and preference integrity."""

import json
import sqlite3
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

import pytest
from asg_evaluation.demo import prepare_demo, synthetic_run
from asg_evaluation.study import StudyRepository
from asg_evaluation.study_design import make_assignments


@pytest.fixture(scope="module")
def frozen_study(tmp_path_factory):
    return prepare_demo(tmp_path_factory.mktemp("study") / "demo", readers=3)


@pytest.fixture
def study(frozen_study, tmp_path):
    destination = tmp_path / "study.sqlite3"
    with sqlite3.connect(frozen_study.path) as source, sqlite3.connect(destination) as target:
        source.backup(target)
    return StudyRepository(destination)


def test_assignments_are_reproducible_blind_balanced_and_connected(study):
    dataset = study.export()
    exposures = {(s["owner"], s["id"]) for s in dataset["stories"] if s["owner"]}
    first = make_assignments(dataset["stories"], dataset["participants"], exposures, 42)
    assert first == make_assignments(dataset["stories"], dataset["participants"], exposures, 42)
    for reader in dataset["participants"]:
        selected = [q for q in first if q["participant"] == reader["id"]]
        story_ids = {s for q in selected for s in (q["left"], q["right"])}
        assert len(story_ids) <= 10
        assert not any((reader["id"], s) in exposures for s in story_ids)
        for criterion in ("H01", "H02", "H03"):
            questions = [q for q in selected if q["criterion"] == criterion]
            assert Counter(q["left"] for q in questions) == Counter(q["right"] for q in questions)
        question = study.next_question(reader["id"])
        assert set(question["left"]) == {"id", "text", "read"}
    assert all(len(c["planned_components"]) == 1 for c in dataset["coverage"].values())
    assert "synthetic-reader-" not in json.dumps(dataset)


def test_votes_survive_restart_and_concurrent_repeated_callbacks(study):
    reader, stranger = study.export()["participants"][:2]
    question = study.next_question(reader["id"])
    with pytest.raises(ValueError, match="lectura"):
        study.vote(reader["id"], question["id"], "A")
    for side in ("left", "right"):
        study.mark_read(reader["id"], question["id"], question[side]["id"])
    study.pause(reader["id"])
    with pytest.raises(ValueError, match="activa"):
        study.vote(reader["id"], question["id"], "A")
    restarted = StudyRepository(study.path)
    restarted.pause(reader["id"], False)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(lambda _: restarted.vote(reader["id"], question["id"], "abstain"), range(2))
        )
    assert sorted(results) == [False, True]
    with pytest.raises(ValueError, match="otro lector"):
        restarted.vote(stranger["id"], question["id"], "A")
    data = restarted.export()
    assert len(data["votes"]) == 1
    progress = restarted.progress(reader["id"])
    assert progress["answered"] == 1 == progress["answered_by_session"][question["session"]]
    assert progress["sessions"] == len(progress["answered_by_session"])
    coverage = data["coverage"][question["criterion"]]
    assert coverage["abstentions"] == 1
    assert sum(coverage["comparisons"].values()) == 0
    assert restarted.next_question(reader["id"])["id"] != question["id"]


def test_known_story_is_excluded_without_deleting_votes(study):
    reader = study.export()["participants"][0]["id"]
    question = study.next_question(reader)
    known = question["left"]["id"]
    study.recognize(reader, question["id"], known)
    assignments = [
        a for a in study.export()["assignments"] if a["participant"] == reader and not a["void"]
    ]
    assert all(known not in (q["left"], q["right"]) for q in assignments)
    with pytest.raises(ValueError):
        study.mark_read(reader, question["id"], known)
    assert not study.export()["votes"]


def test_freeze_rejects_changed_inputs_and_locked_study_rejects_new_stories(study, tmp_path):
    data = study.export()
    with pytest.raises(ValueError):
        study.add_story(synthetic_run(tmp_path / "late", 30))
    stories = data["stories"]
    with study.transaction() as db:
        paths = {r["id"]: r["run_path"] for r in db.execute("SELECT id,run_path FROM stories")}
    for story in stories:
        story["run_path"] = paths[story["id"]]
    with pytest.raises(ValueError, match="versión"):
        study._validate_pool(stories, data["participants"], "WRONG")
    stories[0]["text_hash"] = "changed"
    with pytest.raises(ValueError, match="cambió"):
        study._validate_pool(stories, data["participants"], "DEMO-1")


def test_contribution_is_unique_replaceable_and_bound_to_the_reserved_job(tmp_path):
    repository = StudyRepository(tmp_path / "study.sqlite3")
    repository.create("test", required_version="DEMO-1")
    repository.transition("collection")
    reader = repository.participant("telegram-user", profile="regular")
    assert repository.contribution(reader["id"]) == {"enrolled": False, "pending": False}
    repository.request_contribution(reader["id"])
    repository.bind_contribution("telegram-user", "failed")
    repository.release_contribution("telegram-user", "failed")
    repository.bind_contribution("telegram-user", "reserved")
    assert repository.contribution(reader["id"]) == {"enrolled": False, "pending": True}
    unrelated = synthetic_run(tmp_path / "unrelated", 1)
    assert not repository.complete_generation("telegram-user", "other", unrelated)
    first = synthetic_run(tmp_path / "first", 2)
    assert repository.complete_generation("telegram-user", "reserved", first)
    assert repository.contribution(reader["id"]) == {"enrolled": True, "pending": False}
    story_id = repository.export()["stories"][0]["id"]
    repository.request_contribution(reader["id"])
    repository.bind_contribution("telegram-user", "second")
    second = synthetic_run(tmp_path / "second", 3)
    assert repository.complete_generation("telegram-user", "second", second)
    stories = repository.export()["stories"]
    assert len(stories) == 1 and stories[0]["id"] == story_id
    assert "3" in stories[0]["text"]
