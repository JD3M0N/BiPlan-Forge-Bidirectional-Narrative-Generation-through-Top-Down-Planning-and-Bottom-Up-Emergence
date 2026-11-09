import os
import subprocess
from pathlib import Path

import pytest
from asg_core.latex import build, main, mirror, summarize


def _write(path: Path, text: str = "x") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _thesis(root: Path) -> Path:
    source = root / "redaccion"
    _write(source / "tesis" / "Thesis.tex", "\\documentclass{article}")
    _write(source / "tesis" / "Graphics" / "uhlogo.pdf", "%PDF logo")
    _write(source / "tablas" / "piloto.tex", "tabla")
    return source


def test_mirror_copies_sources_drops_stale_ones_and_keeps_build_outputs(tmp_path):
    source = _thesis(tmp_path)
    _write(source / "tesis" / "Thesis.aux", "stale aux from E:")
    _write(source / "tesis" / "Thesis.pdf", "old pdf")
    _write(source / "presentaciones" / "slides.tex")
    target = tmp_path / "build" / "redaccion"
    _write(target / "tesis" / "Borrado.tex", "deleted from the source")
    _write(target / "tesis" / "Thesis.aux", "aux of the previous build")

    assert mirror(source, target) == 3
    assert (target / "tesis" / "Graphics" / "uhlogo.pdf").read_text() == "%PDF logo"
    assert (target / "tablas" / "piloto.tex").exists()
    assert not (target / "tesis" / "Thesis.pdf").exists()
    assert not (target / "presentaciones").exists()
    assert not (target / "tesis" / "Borrado.tex").exists()
    assert (target / "tesis" / "Thesis.aux").read_text() == "aux of the previous build"

    # A second mirror copies only what changed, so latexmk does not rerun everything.
    assert mirror(source, target) == 0
    edited = _write(source / "tablas" / "piloto.tex", "tabla corregida")
    os.utime(edited, (edited.stat().st_atime, edited.stat().st_mtime + 5))
    assert mirror(source, target) == 1


def test_summarize_reads_the_last_pass_of_a_wrapped_log():
    log = "\n".join(
        [
            "LaTeX Warning: Reference `fig:paquetes' on page 33 undefined on input line 36.",
            "LaTeX Warning: Citation `piad2026' on page 2 undefined on inpu",
            "t line 9.",
            "Overfull \\hbox (2.3679pt too wide) in paragraph at lines 16--16",
            "! TeX capacity exceeded, sorry [input stack size=10000].",
            "Output written on Thesis.pdf (80 pages, 863467 bytes).",
        ]
    )
    summary = summarize(log)
    assert summary.pages == 80
    assert summary.errors == ("TeX capacity exceeded, sorry [input stack size=10000].",)
    assert (summary.undefined, summary.overfull) == (2, 1)
    assert summarize("").pages is None


@pytest.mark.parametrize(("code", "pdf_back"), [(0, True), (12, False)])
def test_build_runs_latexmk_in_the_copy_and_returns_the_pdf_only_on_success(
    tmp_path, code, pdf_back
):
    source = _thesis(tmp_path)
    _write(source / "tesis" / "Thesis.pdf", "previous good pdf")
    calls = []

    def fake_latexmk(command, *, cwd, check):
        """Record the call and leave the outputs a real latexmk would write."""
        calls.append((command, Path(cwd)))
        _write(Path(cwd) / "Thesis.pdf", "new pdf")
        _write(Path(cwd) / "Thesis.log", "Output written on Thesis.pdf (3 pages, 10 bytes).")
        return subprocess.CompletedProcess(command, code)

    returned, summary = build(source, tmp_path / "build", "latexmk", run=fake_latexmk)

    assert calls == [
        (["latexmk", "-silent", "Thesis.tex"], tmp_path / "build" / "redaccion" / "tesis")
    ]
    assert returned == code and summary.pages == 3
    assert (source / "tesis" / "Thesis.log").exists()
    expected = "new pdf" if pdf_back else "previous good pdf"
    assert (source / "tesis" / "Thesis.pdf").read_text() == expected


def test_main_explains_a_missing_thesis_or_latexmk(tmp_path, monkeypatch, capsys):
    assert main(["--source", str(tmp_path)]) == 2
    assert "No se encuentra" in capsys.readouterr().out

    monkeypatch.setattr("asg_core.latex.shutil.which", lambda name: None)
    assert main(["--source", str(_thesis(tmp_path))]) == 2
    assert "latexmk" in capsys.readouterr().out
