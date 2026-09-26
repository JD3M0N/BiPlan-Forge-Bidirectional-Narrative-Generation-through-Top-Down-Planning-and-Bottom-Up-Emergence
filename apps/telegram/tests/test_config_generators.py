import pytest
from asg_telegram.config import TelegramConfigurationError, load_settings
from asg_telegram.generators import DEFAULT_REGISTRY, GeneratorRegistry


def test_load_settings_reads_the_token_or_fails_without_leaking_it(tmp_path, monkeypatch):
    (tmp_path / "packages").mkdir()
    (tmp_path / "Stories").mkdir()
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("STORY_GENERATOR", raising=False)

    with pytest.raises(TelegramConfigurationError, match="TELEGRAM_BOT_TOKEN"):
        load_settings(tmp_path)

    (tmp_path / ".env").write_text(
        "TELEGRAM_BOT_TOKEN=secret-token\nSTORY_GENERATOR=STAGECRAFT\n",
        encoding="utf-8",
    )
    settings = load_settings(tmp_path)
    assert settings.telegram_token == "secret-token"
    assert settings.generator_name == "stagecraft"
    assert "secret-token" not in repr(TelegramConfigurationError("error"))


def test_the_pre_rename_generator_name_still_resolves():
    """A deployed STORY_GENERATOR=top-down must keep starting the bot after the rename."""
    assert {"stagecraft", "top-down"} <= set(DEFAULT_REGISTRY.available)


def test_registry_selects_custom_generator_and_lists_unknown_names():
    expected = object()
    registry = GeneratorRegistry()
    registry.register("fake", lambda: expected)
    assert registry.create("FAKE") is expected
    with pytest.raises(ValueError, match=r"Disponibles: fake"):
        registry.create("missing")
