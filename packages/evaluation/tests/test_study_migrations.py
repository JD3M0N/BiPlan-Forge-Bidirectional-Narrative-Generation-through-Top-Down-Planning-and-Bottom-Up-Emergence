"""Schema migration, curated ownership and pre-freeze edits preserve research identity."""

import sqlite3

import pytest
from asg_evaluation.demo import synthetic_run
from asg_evaluation.study import SCHEMA_VERSION, StudyRepository


def test_schema_one_migrates_and_curated_ownership_does_not_replace_contribution(tmp_path):
    path = tmp_path / "study.sqlite3"
    repository = StudyRepository(path)
    repository.create("migration", required_version="DEMO-1")
    with sqlite3.connect(path) as db:
        db.execute("DROP INDEX contribution_owner")
        db.execute(
            "CREATE UNIQUE INDEX contribution_owner ON stories(owner) WHERE owner IS NOT NULL"
        )
        db.execute("PRAGMA user_version=1")
    repository = StudyRepository(path)
    with sqlite3.connect(path) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
    owner = repository.participant("author", profile="regular")["id"]
    repository.participant("author", is_author=True)
    assert repository.export()["participants"][0]["is_author"] == 1
    for i in range(2):
        repository.add_story(synthetic_run(tmp_path / str(i), i), owner=owner, curated=True)
    run = synthetic_run(tmp_path / "contribution", 3)
    identity = repository.add_story(run, owner=owner)
    (run / "story.md").write_text("Texto actualizado antes de congelar.", encoding="utf-8")
    assert repository.add_story(run, owner=owner) == identity
    assert len(repository.export()["stories"]) == 3
    with pytest.raises(ValueError):
        repository.add_story(run, owner=None)
