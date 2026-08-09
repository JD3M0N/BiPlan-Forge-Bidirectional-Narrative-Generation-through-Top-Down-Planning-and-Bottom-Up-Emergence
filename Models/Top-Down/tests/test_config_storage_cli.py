import json
from pathlib import Path

import pytest

from asg_top_down import cli
from asg_top_down.config import find_project_root, load_settings
from asg_top_down.errors import ConfigurationError
from asg_top_down.storage import ArtifactRepository, slugify


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
        }


def test_settings_require_api_key(tmp_path, monkeypatch) -> None:
    (tmp_path / "Models").mkdir()
    (tmp_path / "Stories").mkdir()
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(ConfigurationError, match="GEMINI_API_KEY"):
        load_settings(tmp_path)


def test_find_project_root_from_nested_path(tmp_path) -> None:
    (tmp_path / "Models").mkdir()
    nested = tmp_path / "Stories" / "Top-Down"
    nested.mkdir(parents=True)
    assert find_project_root(nested) == tmp_path


def test_cli_rejects_empty_prompt(monkeypatch, capsys) -> None:
    monkeypatch.setattr("builtins.input", lambda _: "")
    assert cli.main() == 2
    assert "no puede estar vacío" in capsys.readouterr().err
