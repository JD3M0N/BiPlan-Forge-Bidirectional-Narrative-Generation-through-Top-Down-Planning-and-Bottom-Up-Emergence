import json
from pathlib import Path

import pytest

from asg_top_down import cli
from asg_top_down.config import find_project_root, load_settings
from asg_top_down.errors import ConfigurationError
from asg_top_down.storage import ArtifactRepository, slugify
from asg_top_down.schemas import StoryRequest
from pydantic import ValidationError


def test_slugify_handles_accents_and_symbols() -> None:
    assert slugify("¡La Señal Cósmica!") == "la-senal-cosmica"


def test_repository_never_serializes_an_api_key(tmp_path) -> None:
    repository = ArtifactRepository(tmp_path, "gemini-test", "Historia")
    data = json.loads(
        (repository.run_dir / "metadata.json").read_text(encoding="utf-8")
    )
    assert set(data) == {
        "run_id",
        "model",
        "created_at",
        "updated_at",
        "status",
            "completed_stages",
            "error",
            "error_code",
            "error_stage",
            "warnings",
            "pipeline_version",
        }
    assert data["pipeline_version"] == "3.1"


def test_settings_require_api_key(tmp_path, monkeypatch) -> None:
    (tmp_path / "Models").mkdir()
    (tmp_path / "Stories").mkdir()
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(ConfigurationError, match="GEMINI_API_KEY"):
        load_settings(tmp_path)


def test_default_target_words_can_be_configured(tmp_path, monkeypatch) -> None:
    (tmp_path / "Models").mkdir()
    (tmp_path / "Stories").mkdir()
    monkeypatch.setenv("GEMINI_API_KEY", "test")
    monkeypatch.setenv("STORY_DEFAULT_WORDS", "2400")
    assert load_settings(tmp_path).default_target_words == 2400


def test_artifact_retries_can_be_configured(tmp_path, monkeypatch) -> None:
    (tmp_path / "Models").mkdir()
    (tmp_path / "Stories").mkdir()
    monkeypatch.setenv("GEMINI_API_KEY", "test")
    monkeypatch.setenv("STORY_MAX_ARTIFACT_RETRIES", "4")
    assert load_settings(tmp_path).max_artifact_retries == 4


@pytest.mark.parametrize("value", ["299", "20001", "no-es-entero"])
def test_default_target_words_rejects_invalid_values(
    tmp_path, monkeypatch, value
) -> None:
    (tmp_path / "Models").mkdir()
    (tmp_path / "Stories").mkdir()
    monkeypatch.setenv("GEMINI_API_KEY", "test")
    monkeypatch.setenv("STORY_DEFAULT_WORDS", value)
    with pytest.raises(ConfigurationError, match="STORY_DEFAULT_WORDS"):
        load_settings(tmp_path)


@pytest.mark.parametrize("target", [299, 20_001])
def test_story_request_rejects_word_limits(target) -> None:
    with pytest.raises(ValidationError):
        StoryRequest(
            original_prompt="Historia", title="Historia", genre="drama",
            tone="serio", premise="Una prueba", target_words=target,
        )


def test_repository_saves_incremental_nested_artifacts(tmp_path) -> None:
    repository = ArtifactRepository(tmp_path, "gemini-test", "Historia")
    repository.save_text("scenes/chapter-001.md", "borrador")
    repository.complete_stage("scenes")
    assert (repository.run_dir / "scenes" / "chapter-001.md").read_text(
        encoding="utf-8"
    ) == "borrador\n"
    metadata = json.loads(
        (repository.run_dir / "metadata.json").read_text(encoding="utf-8")
    )
    assert metadata["completed_stages"] == ["scenes"]


def test_find_project_root_from_nested_path(tmp_path) -> None:
    (tmp_path / "Models").mkdir()
    nested = tmp_path / "Stories" / "Top-Down"
    nested.mkdir(parents=True)
    assert find_project_root(nested) == tmp_path


def test_cli_rejects_empty_prompt(monkeypatch, capsys) -> None:
    monkeypatch.setattr("builtins.input", lambda _: "")
    assert cli.main() == 2
    assert "no puede estar vacío" in capsys.readouterr().err
