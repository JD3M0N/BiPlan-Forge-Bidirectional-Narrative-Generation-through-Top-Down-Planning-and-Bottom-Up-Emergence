"""The feature CLI keeps measuring a corpus when one text cannot be segmented."""

from pathlib import Path
from types import SimpleNamespace

import asg_stagecraft.tools.extract_features as cli
import pytest
from asg_stagecraft.runtime.errors import ProviderOverloadedError


def test_an_invalid_text_does_not_stop_the_rest(monkeypatch, capsys):
    sources = [("roto", Path("a.json")), ("sano", Path("b.json"))]
    measured = []

    def extract(text, provider, **kwargs):
        if text == "roto":
            raise ValueError("Unassigned paragraphs")
        measured.append(text)
        return {"complete": True}

    monkeypatch.setattr(cli, "_sources", lambda args: sources)
    monkeypatch.setattr(cli, "load_settings", lambda: SimpleNamespace(model="fake"))
    monkeypatch.setattr(cli, "provider_from_settings", lambda settings: None)
    monkeypatch.setattr(cli, "extract_features", extract)
    assert cli.main(["--root", "."]) == 1
    assert measured == ["sano"]
    out = capsys.readouterr().out
    assert "a.json: incompleta (Unassigned paragraphs)" in out
    assert "b.json: completa" in out


def test_a_provider_failure_still_stops_the_corpus(monkeypatch):
    calls = []

    def extract(text, provider, **kwargs):
        calls.append(text)
        raise ProviderOverloadedError("saturado")

    monkeypatch.setattr(cli, "_sources", lambda args: [("a", Path("a")), ("b", Path("b"))])
    monkeypatch.setattr(cli, "load_settings", lambda: SimpleNamespace(model="fake"))
    monkeypatch.setattr(cli, "provider_from_settings", lambda settings: None)
    monkeypatch.setattr(cli, "extract_features", extract)
    assert cli.main(["--root", "."]) == 1
    assert calls == ["a"]


@pytest.fixture(autouse=True)
def _utf8(monkeypatch):
    """Keep the CLI from reconfiguring pytest's captured streams."""
    monkeypatch.setattr(cli, "use_utf8_output", lambda: None)
