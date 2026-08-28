"""Tests for shared filesystem infrastructure."""

import json

from asg_core import atomic_write_json, atomic_write_text, find_project_root, slugify, stories_path


def test_find_project_root_and_story_path(tmp_path):
    """Resolve the repository marker and build a story path below it."""
    (tmp_path / "packages").mkdir()
    (tmp_path / "Stories").mkdir()
    nested = tmp_path / "apps" / "telegram"
    nested.mkdir(parents=True)

    assert find_project_root(nested) == tmp_path
    assert stories_path("Top-Down", root=tmp_path) == tmp_path / "Stories" / "Top-Down"


def test_slugify_uses_ascii_and_fallback():
    """Normalize accented names and provide a stable empty-value fallback."""
    assert slugify("La habitación final") == "la-habitacion-final"
    assert slugify("***", fallback="story") == "story"


def test_atomic_writers_replace_complete_files(tmp_path):
    """Persist text and JSON without leaving temporary files behind."""
    text_path = atomic_write_text(tmp_path / "note.txt", "hello")
    json_path = atomic_write_json(tmp_path / "data.json", {"value": "á"})

    assert text_path.read_text(encoding="utf-8") == "hello"
    assert json.loads(json_path.read_text(encoding="utf-8")) == {"value": "á"}
    assert not list(tmp_path.glob("*.tmp"))
