import json

import pytest
from asg_top_down.config import load_settings
from asg_top_down.errors import ConfigurationError
from asg_top_down.generator import StoryRun
from asg_top_down.storage import ArtifactRepository


def project(tmp_path):
    (tmp_path / "packages").mkdir()
    (tmp_path / "Stories").mkdir()
    return tmp_path


def test_settings_are_reduced_to_runtime_generation_values(tmp_path, monkeypatch) -> None:
    root = project(tmp_path)
    monkeypatch.setenv("GEMINI_API_KEY", "secret")
    monkeypatch.setenv("STORY_DEFAULT_WORDS", "1200")
    settings = load_settings(root)
    assert settings.default_target_words == 1200
    assert set(settings.__dataclass_fields__) == {
        "api_key",
        "model",
        "output_root",
        "rpm_limit",
        "rpm_reserve",
        "tpm_limit",
        "max_retries",
        "max_retry_delay",
        "request_timeout_ms",
        "default_target_words",
    }


def test_missing_api_key_is_actionable(tmp_path, monkeypatch) -> None:
    root = project(tmp_path)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(ConfigurationError, match="GEMINI_API_KEY"):
        load_settings(root)


def test_repository_versions_new_runs_as_5(tmp_path) -> None:
    repository = ArtifactRepository(tmp_path, "model", "Historia")
    metadata = json.loads((repository.run_dir / "metadata.json").read_text(encoding="utf-8"))
    manifest = json.loads(
        (repository.run_dir / "pipeline_manifest.json").read_text(encoding="utf-8")
    )
    assert metadata["pipeline_version"] == "5.0"
    assert manifest["pipeline_version"] == "5.0"


def test_story_run_rejects_old_or_incomplete_metadata(tmp_path) -> None:
    run_dir = tmp_path / "old"
    run_dir.mkdir()
    (run_dir / "metadata.json").write_text(
        json.dumps({"status": "completed", "pipeline_version": "4.1"}),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="5.0"):
        StoryRun(run_dir)
