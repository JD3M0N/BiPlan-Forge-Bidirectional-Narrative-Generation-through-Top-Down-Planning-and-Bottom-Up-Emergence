import json
from pathlib import Path

import pytest

from asg_top_down import cli
from asg_top_down.config import find_project_root, load_settings
from asg_top_down.errors import ConfigurationError
from asg_top_down.errors import ArtifactValidationError
from asg_top_down.generator import StoryRun
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
    assert data["pipeline_version"] == "4.1"


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


def test_request_timeout_can_be_configured(tmp_path, monkeypatch) -> None:
    (tmp_path / "Models").mkdir()
    (tmp_path / "Stories").mkdir()
    monkeypatch.setenv("GEMINI_API_KEY", "test")
    monkeypatch.setenv("GEMINI_REQUEST_TIMEOUT_MS", "45000")
    assert load_settings(tmp_path).request_timeout_ms == 45_000


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


def test_story_request_reads_legacy_json_without_processed_prompt() -> None:
    request = StoryRequest.model_validate_json(json.dumps({
        "original_prompt": "Historia", "title": "Historia", "language": "español",
        "genre": "drama", "tone": "serio", "premise": "Una prueba",
    }))
    assert request.original_prompt == "Historia"
    assert request.processed_prompt == ""


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
    manifest = json.loads(
        (repository.run_dir / "pipeline_manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["completed_stages"] == ["scenes"]
    assert len(manifest["artifacts"]["scenes/chapter-001.md"]["sha256"]) == 64
    assert not list(repository.run_dir.rglob("*.tmp"))


def test_repository_announces_artifact_only_after_atomic_write(tmp_path) -> None:
    received = []
    repository = None

    def announce(filename, created):
        received.append((filename, created, (repository.run_dir / filename).is_file()))

    repository = ArtifactRepository(
        tmp_path, "gemini-test", "Historia", on_artifact=announce,
    )
    repository.save_text("notes/result.md", "primero")
    repository.save_text("notes/result.md", "segundo")
    assert received == [
        ("notes/result.md", True, True),
        ("notes/result.md", False, True),
    ]


def test_find_project_root_from_nested_path(tmp_path) -> None:
    (tmp_path / "Models").mkdir()
    nested = tmp_path / "Stories" / "Top-Down"
    nested.mkdir(parents=True)
    assert find_project_root(nested) == tmp_path


def test_story_run_reads_completed_v3_but_rejects_incomplete_runs(tmp_path) -> None:
    completed = tmp_path / "completed-v3"
    completed.mkdir()
    (completed / "metadata.json").write_text(
        json.dumps({"pipeline_version": "3.3"}), encoding="utf-8",
    )
    (completed / "story.md").write_text("## Historia\n\nFin", encoding="utf-8")
    assert StoryRun(completed).story_path.is_file()
    incomplete = tmp_path / "incomplete-v3"
    incomplete.mkdir()
    (incomplete / "metadata.json").write_text(
        json.dumps({"pipeline_version": "3.3"}), encoding="utf-8",
    )
    with pytest.raises(ArtifactValidationError, match="incompleta"):
        StoryRun(incomplete)


def test_cli_rejects_empty_prompt(monkeypatch, capsys) -> None:
    monkeypatch.setattr("builtins.input", lambda _: "")
    assert cli.main() == 2
    assert "no puede estar vacío" in capsys.readouterr().err
