import json

import pytest
from asg_evaluation import (
    METRICS,
    add_evaluation,
    create_evaluation_template,
    discover_stories,
)


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


@pytest.mark.parametrize("value", [0, 11, 1.5, True, None])
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
