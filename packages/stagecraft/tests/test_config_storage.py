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


@pytest.mark.parametrize(
    ("env", "match"),
    [
        ({"GEMINI_API_KEY": None}, "GEMINI_API_KEY"),
        ({"ASG_STORY_FORMAT": "screenplay"}, "ASG_STORY_FORMAT"),
        ({"ASG_SCRIPT_METHOD": "improvised"}, "ASG_SCRIPT_METHOD"),
        ({"GEMINI_STAGE_RPM_LIMIT": "many"}, "GEMINI_STAGE_RPM_LIMIT"),
        ({"ASG_LLM_CHAIN": "gemini,groq", "GROQ_API_KEY": None}, "GROQ_API_KEY"),
        ({"ASG_LLM_CHAIN": "gemini,openrouter"}, "ASG_LLM_CHAIN"),
    ],
    ids=[
        "missing-api-key",
        "invalid-story-format",
        "invalid-script-method",
        "invalid-stage-rpm",
        "chain-provider-without-key",
        "unknown-chain-provider",
    ],
)
def test_a_bad_environment_variable_names_itself(tmp_path, monkeypatch, env, match) -> None:
    root = project(tmp_path)
    monkeypatch.setenv("GEMINI_API_KEY", "secret")
    for name, value in env.items():
        if value is None:
            monkeypatch.delenv(name, raising=False)
        else:
            monkeypatch.setenv(name, value)
    with pytest.raises(ConfigurationError, match=match):
        load_settings(root)


@pytest.mark.parametrize(
    ("story_format", "script_method", "expected_format", "expected_method"),
    [
        (None, None, StoryFormat.NARRATIVE, ScriptMethod.NATIVE),
        ("Script", "ADAPTED", StoryFormat.SCRIPT, ScriptMethod.ADAPTED),
    ],
    ids=["defaults-when-unset", "reads-case-insensitively-when-set"],
)
def test_output_format_defaults_and_reads_environment_case_insensitively(
    tmp_path, monkeypatch, story_format, script_method, expected_format, expected_method
) -> None:
    root = project(tmp_path)
    monkeypatch.setenv("GEMINI_API_KEY", "secret")
    for name, value in (("ASG_STORY_FORMAT", story_format), ("ASG_SCRIPT_METHOD", script_method)):
        if value is None:
            monkeypatch.delenv(name, raising=False)
        else:
            monkeypatch.setenv(name, value)
    settings = load_settings(root)
    assert settings.story_format is expected_format
    assert settings.script_method is expected_method


STAGE_VARIABLES = ("GEMINI_STAGE_MODEL", "GEMINI_STAGE_API_KEY", "GEMINI_STAGE_RPM_LIMIT")


def test_an_unset_performance_model_inherits_the_main_one(tmp_path, monkeypatch) -> None:
    root = project(tmp_path)
    monkeypatch.setenv("GEMINI_API_KEY", "secret")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
    for name in STAGE_VARIABLES:
        monkeypatch.delenv(name, raising=False)
    settings = load_settings(root)
    assert settings.effective_stage_model == "gemini-3.5-flash-lite"
    assert settings.effective_stage_api_key == "secret"
    assert settings.effective_stage_rpm_limit == settings.rpm_limit
    assert not settings.splits_stage
    assert settings.model_summary(simulated=True) == "gemini-3.5-flash-lite"


def test_the_performance_reads_its_own_model_key_and_pace(tmp_path, monkeypatch) -> None:
    root = project(tmp_path)
    monkeypatch.setenv("GEMINI_API_KEY", "secret")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
    monkeypatch.setenv("GEMINI_STAGE_MODEL", " gemini-3.1-flash-lite ")
    monkeypatch.setenv("GEMINI_STAGE_API_KEY", "stage-secret")
    monkeypatch.setenv("GEMINI_STAGE_RPM_LIMIT", "10")
    settings = load_settings(root)
    assert settings.effective_stage_model == "gemini-3.1-flash-lite"
    assert settings.effective_stage_api_key == "stage-secret"
    assert settings.effective_stage_rpm_limit == 10
    assert settings.splits_stage
    assert settings.model_summary(simulated=True) == (
        "gemini-3.5-flash-lite (función: gemini-3.1-flash-lite)"
    )
    # Only a simulated run has a performance, so any other run names the main model alone.
    assert settings.model_summary(simulated=False) == "gemini-3.5-flash-lite"


def test_a_blank_number_keeps_its_default(tmp_path, monkeypatch) -> None:
    """.env.example leaves GEMINI_STAGE_RPM_LIMIT blank; a copied example must still load."""
    root = project(tmp_path)
    monkeypatch.setenv("GEMINI_API_KEY", "secret")
    monkeypatch.setenv("GEMINI_STAGE_RPM_LIMIT", "")
    monkeypatch.setenv("GEMINI_RPM_LIMIT", "  ")
    settings = load_settings(root)
    assert settings.stage_rpm_limit == 0
    assert settings.rpm_limit == 15
    # Per model: with GEMINI_STAGE_MODEL the Gemini total the quota panel shows is 1000.
    assert settings.gemini_daily_requests == 500


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
