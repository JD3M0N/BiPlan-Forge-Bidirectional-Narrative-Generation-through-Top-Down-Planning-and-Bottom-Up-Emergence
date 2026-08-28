import pytest
from asg_telegram.config import TelegramConfigurationError, load_settings
from asg_telegram.generators import GeneratorRegistry


def test_load_settings_reads_token_and_generator(tmp_path, monkeypatch):
    (tmp_path / "packages").mkdir()
    (tmp_path / "Stories").mkdir()
    (tmp_path / ".env").write_text(
        "TELEGRAM_BOT_TOKEN=secret-token\nSTORY_GENERATOR=TOP-DOWN\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("STORY_GENERATOR", raising=False)
    settings = load_settings(tmp_path)
    assert settings.telegram_token == "secret-token"
    assert settings.generator_name == "top-down"
    assert "secret-token" not in repr(TelegramConfigurationError("error"))


def test_missing_token_has_safe_error(tmp_path, monkeypatch):
    (tmp_path / "packages").mkdir()
    (tmp_path / "Stories").mkdir()
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    with pytest.raises(TelegramConfigurationError, match="TELEGRAM_BOT_TOKEN"):
        load_settings(tmp_path)


def test_registry_selects_custom_generator_and_lists_unknown_names():
    expected = object()
    registry = GeneratorRegistry()
    registry.register("fake", lambda: expected)
    assert registry.create("FAKE") is expected
    with pytest.raises(ValueError, match=r"Disponibles: fake"):
        registry.create("missing")
