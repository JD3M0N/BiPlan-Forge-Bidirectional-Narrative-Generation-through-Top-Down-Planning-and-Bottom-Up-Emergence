import hashlib
import json
from importlib.metadata import version
from pathlib import Path

import pytest
from asg_stagecraft import __version__
from asg_stagecraft.formats import ScriptMethod, StoryFormat
from asg_stagecraft.generator import StoryRun
from asg_stagecraft.runtime.config import load_settings
from asg_stagecraft.runtime.errors import ConfigurationError, RunArtifactError
from asg_stagecraft.runtime.storage import ArtifactRepository
from asg_stagecraft.version import GENERATOR_NAME, GENERATOR_VERSION, PIPELINE_VERSION


def project(tmp_path):
    (tmp_path / "packages").mkdir()
    (tmp_path / "Stories").mkdir()
    return tmp_path


def test_settings_never_carry_legacy_length_budget_fields(tmp_path, monkeypatch) -> None:
    root = project(tmp_path)
    monkeypatch.setenv("GEMINI_API_KEY", "secret")
    settings = load_settings(root)
    assert "target_words" not in settings.__dataclass_fields__


def test_missing_api_key_is_actionable(tmp_path, monkeypatch) -> None:
    root = project(tmp_path)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(ConfigurationError, match="GEMINI_API_KEY"):
        load_settings(root)


def test_output_format_defaults_to_narrative_and_native(tmp_path, monkeypatch) -> None:
    root = project(tmp_path)
    monkeypatch.setenv("GEMINI_API_KEY", "secret")
    monkeypatch.delenv("ASG_STORY_FORMAT", raising=False)
    monkeypatch.delenv("ASG_SCRIPT_METHOD", raising=False)
    settings = load_settings(root)
    assert settings.story_format is StoryFormat.NARRATIVE
    assert settings.script_method is ScriptMethod.NATIVE


def test_output_format_reads_environment_case_insensitively(tmp_path, monkeypatch) -> None:
    root = project(tmp_path)
    monkeypatch.setenv("GEMINI_API_KEY", "secret")
    monkeypatch.setenv("ASG_STORY_FORMAT", "Script")
    monkeypatch.setenv("ASG_SCRIPT_METHOD", "ADAPTED")
    settings = load_settings(root)
    assert settings.story_format is StoryFormat.SCRIPT
    assert settings.script_method is ScriptMethod.ADAPTED


def test_invalid_story_format_names_the_variable(tmp_path, monkeypatch) -> None:
    root = project(tmp_path)
    monkeypatch.setenv("GEMINI_API_KEY", "secret")
    monkeypatch.setenv("ASG_STORY_FORMAT", "screenplay")
    with pytest.raises(ConfigurationError, match="ASG_STORY_FORMAT"):
        load_settings(root)


def test_invalid_script_method_names_the_variable(tmp_path, monkeypatch) -> None:
    root = project(tmp_path)
    monkeypatch.setenv("GEMINI_API_KEY", "secret")
    monkeypatch.setenv("ASG_SCRIPT_METHOD", "improvised")
    with pytest.raises(ConfigurationError, match="ASG_SCRIPT_METHOD"):
        load_settings(root)


def test_repository_versions_new_runs_to_match_the_installed_package(tmp_path) -> None:
    repository = ArtifactRepository(tmp_path, "model", "Historia")
    metadata = json.loads((repository.run_dir / "metadata.json").read_text(encoding="utf-8"))
    generator = json.loads(
        (repository.run_dir / "generator_version.json").read_text(encoding="utf-8")
    )
    manifest = json.loads(
        (repository.run_dir / "pipeline_manifest.json").read_text(encoding="utf-8")
    )
    assert generator == {
        "generator": GENERATOR_NAME,
        "generator_version": GENERATOR_VERSION,
        "pipeline_version": PIPELINE_VERSION,
    }
    assert metadata["pipeline_version"] == PIPELINE_VERSION
    assert manifest["pipeline_version"] == PIPELINE_VERSION
    assert "generator_version.json" in manifest["artifacts"]
    assert __version__ == GENERATOR_VERSION == version("asg-stagecraft")


def test_appending_a_line_never_rereads_the_log(tmp_path, monkeypatch) -> None:
    """ING-4: every turn reread and rewrote turns.jsonl whole, quadratic in a run's length."""
    repository = ArtifactRepository(tmp_path, "model", "Historia")
    for number in range(3):
        repository.append_jsonl("stage/scene-1/turns.jsonl", {"n": number})
    reads: list[str] = []
    read_text, read_bytes = Path.read_text, Path.read_bytes
    monkeypatch.setattr(
        Path, "read_text", lambda self, *a, **k: reads.append(self.name) or read_text(self, *a, **k)
    )
    monkeypatch.setattr(
        Path, "read_bytes", lambda self: reads.append(self.name) or read_bytes(self)
    )
    repository.append_jsonl("stage/scene-1/turns.jsonl", {"n": 3})
    assert "turns.jsonl" not in reads
    monkeypatch.undo()

    content = (repository.run_dir / "stage" / "scene-1" / "turns.jsonl").read_bytes()
    manifest = json.loads(
        (repository.run_dir / "pipeline_manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["artifacts"]["stage/scene-1/turns.jsonl"] == {
        "sha256": hashlib.sha256(content).hexdigest(),
        "bytes": len(content),
    }
    assert content.decode("utf-8").splitlines() == [json.dumps({"n": n}) for n in range(4)]


@pytest.mark.parametrize(
    ("metadata_text", "match"),
    [
        (json.dumps({"status": "completed", "pipeline_version": "4.1"}), "5.0"),
        (json.dumps({"status": "running", "pipeline_version": "5.1"}), "completed"),
        (None, "metadata.json"),
        ("{not valid json", "metadata.json"),
    ],
    ids=["unsupported-old-version", "not-completed", "missing-file", "corrupt-json"],
)
def test_story_run_rejects_incompatible_metadata(tmp_path, metadata_text, match) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    if metadata_text is not None:
        (run_dir / "metadata.json").write_text(metadata_text, encoding="utf-8")
    with pytest.raises(RunArtifactError, match=match):
        StoryRun(run_dir)


def test_story_run_accepts_current_completed_metadata(tmp_path) -> None:
    run_dir = tmp_path / "compatible"
    run_dir.mkdir()
    (run_dir / "metadata.json").write_text(
        json.dumps({"status": "completed", "pipeline_version": "5.0"}),
        encoding="utf-8",
    )
    assert StoryRun(run_dir).run_dir == run_dir
