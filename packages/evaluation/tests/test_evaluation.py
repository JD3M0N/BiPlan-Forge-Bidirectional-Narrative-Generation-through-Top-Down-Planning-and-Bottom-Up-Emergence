import json
from concurrent.futures import ThreadPoolExecutor

import pytest
from asg_evaluation import (
    METRICS,
    add_evaluation,
    create_evaluation_template,
    discover_stories,
)
from asg_evaluation.evaluation import SCHEMA_VERSION


def scores(value=8):
    return dict.fromkeys(METRICS, value)


def test_template_creation_is_idempotent(tmp_path):
    story = tmp_path / "Top-Down" / "run"
    story.mkdir(parents=True)
    (story / "story.md").write_text("Historia", encoding="utf-8")
    first = create_evaluation_template(story)
    original = first.read_text(encoding="utf-8")
    assert create_evaluation_template(story) == first
    assert first.read_text(encoding="utf-8") == original
    assert discover_stories(tmp_path) == [story]


def test_first_evaluation_replaces_template_and_next_is_appended(tmp_path):
    story = tmp_path / "story"
    story.mkdir()
    (story / "story.md").write_text("Historia", encoding="utf-8")
    add_evaluation(story, " ana ", scores())
    add_evaluation(story, "Luis", scores(9))
    document = json.loads((story / "evaluation.json").read_text(encoding="utf-8"))
    assert [item["user"] for item in document["evaluations"]] == ["ana", "Luis"]
    assert document["evaluations"][0]["coherence"] == 8


@pytest.mark.parametrize(
    "value",
    [0, 11, True],
    ids=["below-range", "above-range", "bool-is-not-a-plain-int"],
)
def test_scores_must_be_integers_from_one_to_ten(tmp_path, value):
    story = tmp_path / "story"
    story.mkdir()
    (story / "story.md").write_text("Historia", encoding="utf-8")
    invalid = scores()
    invalid["coherence"] = value
    with pytest.raises(ValueError, match="coherence"):
        add_evaluation(story, "Ana", invalid)


def test_user_and_exact_metric_names_are_required(tmp_path):
    story = tmp_path / "story"
    story.mkdir()
    (story / "story.md").write_text("Historia", encoding="utf-8")
    with pytest.raises(ValueError, match="user"):
        add_evaluation(story, " ", scores())
    incomplete = scores()
    incomplete.pop("pacing")
    with pytest.raises(ValueError, match="exactamente"):
        add_evaluation(story, "Ana", incomplete)


def test_failed_replace_preserves_existing_file(tmp_path, monkeypatch):
    story = tmp_path / "story"
    story.mkdir()
    (story / "story.md").write_text("Historia", encoding="utf-8")
    destination = create_evaluation_template(story)
    original = destination.read_text(encoding="utf-8")
    monkeypatch.setattr(
        "asg_core.files.os.replace",
        lambda *_: (_ for _ in ()).throw(OSError("boom")),
    )
    with pytest.raises(OSError, match="boom"):
        add_evaluation(story, "Ana", scores())
    assert destination.read_text(encoding="utf-8") == original


def story_with_document(tmp_path, evaluations):
    directory = tmp_path / "story"
    directory.mkdir(exist_ok=True)
    (directory / "story.md").write_text("Historia", encoding="utf-8")
    (directory / "evaluation.json").write_text(
        json.dumps({"schema_version": SCHEMA_VERSION, "evaluations": evaluations}),
        encoding="utf-8",
    )
    return directory


def test_a_template_holding_only_the_evaluator_name_still_accepts_scores(tmp_path):
    story = story_with_document(tmp_path, [{"user": "ana", **dict.fromkeys(METRICS)}])
    add_evaluation(story, "Luis", scores(7))
    document = json.loads((story / "evaluation.json").read_text(encoding="utf-8"))
    assert document["evaluations"] == [{"user": "Luis", **scores(7)}]


def test_a_pending_entry_is_dropped_from_any_position(tmp_path):
    story = story_with_document(
        tmp_path,
        [
            {"user": "ana", **scores(6)},
            {"user": None, **dict.fromkeys(METRICS)},
        ],
    )
    add_evaluation(story, "Luis", scores(7))
    document = json.loads((story / "evaluation.json").read_text(encoding="utf-8"))
    assert [item["user"] for item in document["evaluations"]] == ["ana", "Luis"]


def test_a_template_missing_metric_keys_is_still_pending(tmp_path):
    story = story_with_document(tmp_path, [{"user": "ana", "coherence": None}])
    add_evaluation(story, "Luis", scores(7))
    document = json.loads((story / "evaluation.json").read_text(encoding="utf-8"))
    assert [item["user"] for item in document["evaluations"]] == ["Luis"]


def test_a_half_scored_entry_names_its_position_and_field(tmp_path):
    partial = {"user": "ana", **scores(8)}
    partial["pacing"] = None
    story = story_with_document(tmp_path, [{"user": None, **dict.fromkeys(METRICS)}, partial])
    original = (story / "evaluation.json").read_text(encoding="utf-8")
    with pytest.raises(ValueError, match="evaluación 2: pacing"):
        add_evaluation(story, "Luis", scores(7))
    assert (story / "evaluation.json").read_text(encoding="utf-8") == original


def test_an_unknown_field_is_named_instead_of_blaming_a_metric(tmp_path):
    story = story_with_document(tmp_path, [{"user": "ana", "comentario": "genial", **scores(8)}])
    with pytest.raises(ValueError, match="campos desconocidos: comentario"):
        add_evaluation(story, "Luis", scores(7))


def test_concurrent_evaluations_are_all_preserved(tmp_path):
    story = tmp_path / "story"
    story.mkdir()
    (story / "story.md").write_text("Historia", encoding="utf-8")
    expected = [f"lector-{index:02d}" for index in range(40)]

    def append(user):
        """Store one evaluation from a worker thread."""
        add_evaluation(story, user, scores(5))

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(append, expected))
    document = json.loads((story / "evaluation.json").read_text(encoding="utf-8"))
    assert sorted(item["user"] for item in document["evaluations"]) == expected


def test_a_foreign_lock_reports_a_busy_file(tmp_path, monkeypatch):
    story = tmp_path / "story"
    story.mkdir()
    (story / "story.md").write_text("Historia", encoding="utf-8")
    (story / "evaluation.json.lock").write_text("999 0", encoding="utf-8")
    monkeypatch.setattr(
        "asg_evaluation.evaluation.file_lock",
        lambda path: _instant_lock(path),
    )
    with pytest.raises(TimeoutError, match="Otra evaluación"):
        add_evaluation(story, "Ana", scores())


def _instant_lock(path):
    """Wrap the shared lock with the short waits a test can afford."""
    from asg_core import file_lock

    return file_lock(path, timeout=0.1, stale_after=30.0, poll=0.01)
