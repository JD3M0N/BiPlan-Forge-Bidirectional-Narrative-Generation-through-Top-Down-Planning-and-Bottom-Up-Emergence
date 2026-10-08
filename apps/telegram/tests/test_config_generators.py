import pytest
from asg_telegram.config import TelegramConfigurationError, load_settings
from asg_telegram.generators import DEFAULT_REGISTRY, GeneratorRegistry

REQUIRED = {
    "TELEGRAM_BOT_TOKEN": "secret-token",
    "TELEGRAM_ACCESS_KEY": "clave-secreta",
    "ASG_EVALUATION_STUDY": "Evaluations/study.sqlite3",
}


@pytest.mark.parametrize("missing", [*REQUIRED, "study file"])
def test_load_settings_requires_token_key_and_study(tmp_path, monkeypatch, missing):
    """The bot only starts as the experiment bot: token, shared key and an existing study."""
    (tmp_path / "packages").mkdir()
    (tmp_path / "Stories").mkdir()
    for name in [*REQUIRED, "STORY_GENERATOR"]:
        monkeypatch.setenv(name, "")  # registers the undo that removes what load_dotenv sets
        monkeypatch.delenv(name)
    values = {**REQUIRED, "STORY_GENERATOR": "STAGECRAFT"}
    values.pop(missing, None)
    (tmp_path / ".env").write_text(
        "".join(f"{key}={value}\n" for key, value in values.items()), encoding="utf-8"
    )
    with pytest.raises(TelegramConfigurationError, match=missing.split()[0][:12]):
        load_settings(tmp_path)

    if missing == "study file":
        (tmp_path / "Evaluations").mkdir()
        (tmp_path / "Evaluations" / "study.sqlite3").write_bytes(b"")
        settings = load_settings(tmp_path)
        assert settings.telegram_token == "secret-token"
        assert settings.generator_name == "stagecraft"
        assert settings.study_path == (tmp_path / "Evaluations" / "study.sqlite3").resolve()
        assert "clave-secreta" not in repr(settings)


def test_the_default_registry_only_offers_stagecraft():
    """The registry no longer carries the pre-rename Railway alias."""
    assert DEFAULT_REGISTRY.available == ("stagecraft",)


def test_registry_selects_custom_generator_and_lists_unknown_names():
    expected = object()
    registry = GeneratorRegistry()
    registry.register("fake", lambda: expected)
    assert registry.create("FAKE") is expected
    with pytest.raises(ValueError, match=r"Disponibles: fake"):
        registry.create("missing")
