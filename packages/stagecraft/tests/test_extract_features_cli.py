"""The feature CLI keeps measuring a corpus when one text cannot be segmented."""

import json
from pathlib import Path
from types import SimpleNamespace

import asg_stagecraft.tools.extract_features as cli
import pytest
from asg_evaluation.catalog import digest
from asg_evaluation.features import extraction_identity
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


def make_run(root: Path, name: str, **metadata) -> Path:
    """Write the minimal run that the corpus inventory reads."""
    run = root / "Stagecraft" / name
    run.mkdir(parents=True)
    fields = {"status": "completed", "story_format": "narrative", "pipeline_version": "7.22"}
    (run / "metadata.json").write_text(json.dumps({**fields, **metadata}), encoding="utf-8")
    (run / "story.md").write_text(f"# {name}\n\nTexto de {name}.", encoding="utf-8")
    return run


@pytest.fixture
def corpus(tmp_path, monkeypatch):
    """Six runs: three ineligible, a 7.9, a 7.20 and a 7.22 baseline."""
    make_run(tmp_path, "guion", story_format="script")
    make_run(tmp_path, "fallido", status="failed")
    make_run(tmp_path, "viejo", pipeline_version="6.6")
    make_run(tmp_path, "siete-nueve", pipeline_version="7.9")
    make_run(tmp_path, "siete-veinte", pipeline_version="7.20")
    make_run(tmp_path, "base", story_format="baseline")
    monkeypatch.setattr(cli, "load_settings", lambda: SimpleNamespace(model="fake"))
    return tmp_path


def launched(monkeypatch, argv: list[str]) -> list[str]:
    """Run the CLI with a fake extractor and return the run names it measured."""
    names = []

    def extract(text, provider, *, output, **kwargs):
        names.append(output.parent.parent.name)
        return {"complete": True}

    monkeypatch.setattr(cli, "provider_from_settings", lambda settings: None)
    monkeypatch.setattr(cli, "extract_features", extract)
    assert cli.main(argv) == 0
    return names


@pytest.mark.parametrize(
    ("flags", "expected"),
    [
        ([], ["base", "siete-nueve", "siete-veinte"]),
        (["--desde", "7.20"], ["base", "siete-veinte"]),
        (["--limite", "2"], ["base", "siete-nueve"]),
    ],
)
def test_eligible_filter_follows_the_ranking_rule(corpus, monkeypatch, flags, expected):
    argv = ["--root", str(corpus), "--elegibles", *flags]
    assert launched(monkeypatch, argv) == expected


def test_reuse_skips_texts_complete_in_the_study(corpus, monkeypatch):
    text = (corpus / "Stagecraft" / "base" / "story.md").read_text(encoding="utf-8")
    report = {"complete": True, "identity": extraction_identity(text, "fake")}
    monkeypatch.setattr(cli, "study_extractions", lambda db: {digest(text): report})
    argv = ["--root", str(corpus), "--elegibles", "--reusar", "study.sqlite3"]
    assert launched(monkeypatch, argv) == ["siete-nueve", "siete-veinte"]


def test_dry_run_classifies_without_a_provider(corpus, monkeypatch, capsys):
    def no_provider(settings):
        raise AssertionError("dry-run created a provider")

    monkeypatch.setattr(cli, "provider_from_settings", no_provider)
    run = corpus / "Stagecraft" / "siete-veinte"
    text = (run / "story.md").read_text(encoding="utf-8")
    sidecar = {"complete": False, "identity": extraction_identity(text, "fake")}
    (run / "features").mkdir()
    (run / "features" / "features.json").write_text(json.dumps(sidecar), encoding="utf-8")
    assert cli.main(["--root", str(corpus), "--elegibles", "--limite", "1", "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "3 textos; modelo fake." in out
    assert "incompletos que se reanudan: 1" in out
    assert "sin extraer: 2" in out
    assert "Pendientes: 3; en este lote: 1." in out
    assert "~4 llamadas" in out and "~36" in out


def test_eligible_needs_a_corpus_root(corpus, capsys):
    assert cli.main(["--root", str(corpus / "Stagecraft" / "base"), "--elegibles"]) == 1
    with pytest.raises(SystemExit):
        cli.main(["--root", str(corpus), "--desde", "7.20"])


@pytest.fixture(autouse=True)
def _utf8(monkeypatch):
    """Keep the CLI from reconfiguring pytest's captured streams."""
    monkeypatch.setattr(cli, "use_utf8_output", lambda: None)
