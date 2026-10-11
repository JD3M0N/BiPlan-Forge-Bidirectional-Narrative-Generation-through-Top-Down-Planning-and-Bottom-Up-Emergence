"""Rolling enrollment, immutable sessions and portable research exports."""

import io
import json
import sqlite3
import zipfile
from concurrent.futures import ThreadPoolExecutor

import pytest
from asg_evaluation import study_cli
from asg_evaluation.demo import synthetic_run
from asg_evaluation.pack import PACK_FORMATS
from asg_evaluation.study import StudyRepository
from asg_evaluation.transfer import export_bundle, import_bundle, split_bundle


def rolling(tmp_path):
    repository = StudyRepository(tmp_path / "study.sqlite3")
    repository.create("rolling", required_version="DEMO-1", mode="rolling")
    repository.transition("collection")
    for index in range(3):
        repository.add_story(synthetic_run(tmp_path / f"seed{index}", index), curated=True)
    return repository


def contribute(repository, tmp_path, index):
    reader = repository.participant(f"telegram-{index}", profile="regular")
    sid = repository.add_story(
        synthetic_run(tmp_path / f"run{index}", index + 10), owner=reader["id"]
    )
    return reader["id"], sid


def finish_question(repository, reader, question):
    for side in ("left", "right"):
        repository.mark_read(reader, question["id"], question[side]["id"])
    repository.vote(reader, question["id"], "A")


def test_eighth_distinct_contribution_opens_once_and_seeds_do_not_count(tmp_path):
    repo = rolling(tmp_path)
    readers = [contribute(repo, tmp_path, i) for i in range(7)]
    first, old = readers[0]
    replacement = repo.add_story(synthetic_run(tmp_path / "replacement", 99), owner=first)
    assert replacement != old
    assert repo.info()["state"] == "collection"
    contribute(repo, tmp_path, 7)
    assert repo.info()["state"] == "evaluation"
    snapshot = repo.info()["snapshot"]
    contribute(repo, tmp_path, 8)
    assert repo.info()["snapshot"] == snapshot
    assert len(repo.export()["stories"]) == 13
    assert sum(s["active"] for s in repo.export()["stories"]) == 12


def test_session_stability_new_pool_and_two_session_limit(tmp_path):
    repo = rolling(tmp_path)
    readers = [contribute(repo, tmp_path, i) for i in range(8)]
    reader, own = readers[0]
    first = repo.next_question(reader)
    assignments = repo.export()["assignments"]
    contribute(repo, tmp_path, 8)
    assert repo.next_question(reader)["id"] == first["id"]
    assert repo.export()["assignments"] == assignments
    first_session = {q[side] for q in assignments for side in ("left", "right")}
    assert own not in first_session
    while (question := repo.next_question(reader)) and question["session"] == 1:
        finish_question(repo, reader, question)
    second_session = {
        q[side]
        for q in repo.export()["assignments"]
        if q["session"] == 2
        for side in ("left", "right")
    }
    assert first_session.isdisjoint(second_session)
    for _ in range(30):
        question = repo.next_question(reader)
        if question is None:
            break
        finish_question(repo, reader, question)
    contribute(repo, tmp_path, 9)
    assert repo.next_question(reader) is None
    assert not repo.session_waiting(reader)
    assert len(repo.export()["sessions"]) == 2
    assert repo.progress(reader)["answered"] == 30


def test_concurrent_session_requests_and_replacement_preserve_votes(tmp_path):
    repo = rolling(tmp_path)
    readers = [contribute(repo, tmp_path, i) for i in range(8)]
    reader = readers[0][0]
    with ThreadPoolExecutor(max_workers=2) as executor:
        questions = list(executor.map(repo.next_question, [reader, reader]))
    assert questions[0]["id"] == questions[1]["id"]
    finish_question(repo, reader, questions[0])
    old = repo.export()
    owner = next(s["owner"] for s in old["stories"] if s["id"] == questions[0]["left"]["id"])
    if owner:
        repo.add_story(synthetic_run(tmp_path / "replacement", 99), owner=owner)
    assert repo.export()["votes"] == old["votes"]
    assert repo.export()["assignments"] == old["assignments"]


def test_portable_bundle_and_numbered_parts_verify_before_writing(tmp_path):
    repo = rolling(tmp_path)
    contribute(repo, tmp_path, 0)
    payload = export_bundle(repo)
    assert b"telegram-0" not in payload
    parts = split_bundle(payload, limit=300)
    for name, content in parts:
        (tmp_path / name).write_bytes(content)
    target = tmp_path / "imported"
    result = import_bundle(tmp_path / parts[0][0], target)
    assert result["stories"] == 4
    data = json.loads((target / "study.json").read_text(encoding="utf-8"))
    assert "telegram-0" not in json.dumps(data)
    assert str(tmp_path) not in json.dumps(data)
    with zipfile.ZipFile(io.BytesIO(payload)) as original:
        files = {name: original.read(name) for name in original.namelist()}
    files["study.json"] = b"{}"
    damaged = tmp_path / "damaged.zip"
    with zipfile.ZipFile(damaged, "w") as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    with pytest.raises(ValueError, match="huella"):
        import_bundle(damaged, tmp_path / "bad")
    assert not (tmp_path / "bad").exists()


def test_publication_requires_separate_consent_and_exact_reviewed_text(tmp_path):
    repo = rolling(tmp_path)
    reader, sid = contribute(repo, tmp_path, 0)
    story = next(s for s in repo.export()["stories"] if s["id"] == sid)
    with pytest.raises(ValueError):
        repo.approve_publication(sid, story["text_hash"])
    repo.publication_consent(reader, True)
    with pytest.raises(ValueError):
        repo.approve_publication(sid, "wrong-hash")
    repo.approve_publication(sid, story["text_hash"])
    assert len(repo.publication_batch()) == 1
    repo.publication_consent(reader, False)
    assert not repo.publication_batch()
    assert repo.contribution(reader)["enrolled"]


def test_old_database_is_backed_up_and_keeps_fixed_mode(tmp_path):
    from asg_evaluation.study import _SCHEMA

    path = tmp_path / "old.sqlite3"
    with sqlite3.connect(path) as db:
        for statement in _SCHEMA:
            db.execute(statement)
        db.execute("INSERT INTO study VALUES ('old','collection',42,'DEMO-1',NULL,'today')")
        db.execute("PRAGMA user_version=2")
    repo = StudyRepository(path)
    assert repo.info()["mode"] == "fixed"
    with sqlite3.connect(path.with_name("old.sqlite3.v2.bak")) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 2
    assert repo.info()["state"] == "collection"


def test_roundtrip_preserves_votes_sessions_and_local_run_paths(tmp_path):
    repo = rolling(tmp_path)
    readers = [contribute(repo, tmp_path, i) for i in range(8)]
    reader = readers[0][0]
    question = repo.next_question(reader)
    finish_question(repo, reader, question)
    source = tmp_path / "study.zip"
    source.write_bytes(export_bundle(repo))
    target = tmp_path / "download"
    import_bundle(source, target)
    restored = StudyRepository(target / "study.sqlite3")
    original = repo.export()
    downloaded = restored.export()
    for key in (
        "stories",
        "participants",
        "assignments",
        "votes",
        "sessions",
        "readings",
        "exposures",
        "coverage",
        "first_contributions",
        "pack",
        "author_requests",
    ):
        assert downloaded[key] == original[key]
    with restored.transaction() as db:
        for row in db.execute("SELECT run_path FROM stories"):
            from pathlib import Path

            assert Path(row[0]).is_relative_to(target)
            assert (Path(row[0]) / "story.md").exists()


def test_duplicate_text_and_incomplete_profile_cannot_count(tmp_path):
    repo = rolling(tmp_path)
    reader, sid = contribute(repo, tmp_path, 0)
    duplicate = synthetic_run(tmp_path / "duplicate", 10)
    other = repo.participant("other", profile="regular")["id"]
    with pytest.raises(ValueError, match="texto"):
        repo.add_story(duplicate, owner=other)
    blank = repo.participant("blank")["id"]
    with pytest.raises(ValueError, match="perfil"):
        repo.add_story(synthetic_run(tmp_path / "blank", 44), owner=blank)
    assert repo.info()["state"] == "collection"
    assert len(repo.export()["first_contributions"]) == 1


def test_concurrent_eighth_and_ninth_open_once(tmp_path):
    repo = rolling(tmp_path)
    for i in range(7):
        contribute(repo, tmp_path, i)
    readers = [repo.participant(f"later-{i}", profile="regular")["id"] for i in range(2)]
    runs = [synthetic_run(tmp_path / f"later{i}", 30 + i) for i in range(2)]
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(repo.add_story, run, owner=reader)
            for run, reader in zip(runs, readers, strict=True)
        ]
        for future in futures:
            future.result()
    assert repo.info()["state"] == "evaluation"
    assert len(repo.export()["first_contributions"]) == 9
    assert not repo.export()["sessions"]


def test_known_story_replacement_uses_recorded_session_pool(tmp_path):
    repo = rolling(tmp_path)
    reader = [contribute(repo, tmp_path, i) for i in range(8)][0][0]
    question = repo.next_question(reader)
    _, later = contribute(repo, tmp_path, 8)
    repo.recognize(reader, question["id"], question["left"]["id"])
    assert all(later not in (q["left"], q["right"]) for q in repo.export()["assignments"])
    assert repo.export()["exposures"]


def test_pack_balances_hidden_formats_opens_at_ten_and_assigns_one_session(tmp_path):
    prompts = tmp_path / "author.json"
    prompts.write_text(
        json.dumps([{"prompt": f"idea {fmt}", "format": fmt} for fmt in PACK_FORMATS * 2]),
        encoding="utf-8",
    )
    db = tmp_path / "study.sqlite3"
    args = ["--db", str(db), "create", "pack", "--version", "DEMO-1", "--mode", "pack"]
    assert study_cli.main([*args, "--author-prompts", str(prompts)]) == 0
    repo = StudyRepository(db)
    repo.transition("collection")
    for request in repo.pending_author_requests():
        job = f"author-{request['slot']}"
        repo.bind_author_job(request["slot"], job)
        run = synthetic_run(tmp_path / job, 50 + request["slot"], story_format=request["format"])
        assert repo.complete_author_generation(job, run)
    readers = []
    for index in range(9):
        external = f"telegram-{index}"
        reader = repo.participant(external, profile="regular")["id"]
        repo.request_contribution(reader)
        fmt = repo.assign_format(reader)
        repo.bind_contribution(external, f"job-{index}")
        assert repo.assign_format(reader) == fmt == repo.assigned_format(external, f"job-{index}")
        readers.append((external, reader, fmt))
    assert [fmt for *_, fmt in readers[:6]] == list(PACK_FORMATS * 3)
    for index, (external, _reader, fmt) in enumerate(readers):
        assert repo.info()["state"] == ("evaluation" if index > 5 else "collection")
        run = synthetic_run(tmp_path / f"run{index}", 10 + index, story_format=fmt)
        assert repo.complete_generation(external, f"job-{index}", run)
    data = repo.export()
    pack = {entry["story"] for entry in data["pack"]}
    assert len(pack) == 10 and len(data["stories"]) == 13
    assert repo.info()["snapshot"]["pack"] == data["pack"]
    with pytest.raises(ValueError, match="Ya aportaste"):
        repo.request_contribution(readers[0][1])
    reader = readers[0][1]
    own = next(s["id"] for s in data["stories"] if s["owner"] == reader)
    assert repo.next_question(reader)["session"] == 1
    shown = {q[side] for q in repo.export()["assignments"] for side in ("left", "right")}
    assert len(shown) == 5 and shown <= pack - {own}
    assert len(repo.export()["assignments"]) == 15
    assert not repo.session_waiting(reader)
