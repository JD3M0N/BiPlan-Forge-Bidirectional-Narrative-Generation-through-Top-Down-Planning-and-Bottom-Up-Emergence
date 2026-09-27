"""Enforce concise English documentation across production Python code."""

from __future__ import annotations

import ast
from pathlib import Path

# Resolved from this file, not the working directory: a relative glob run from anywhere but the
# repository root found no module at all, and the gate passed on nothing.
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PRODUCTION_ROOTS = (REPOSITORY_ROOT / "packages", REPOSITORY_ROOT / "apps")
# Words that give away a Spanish docstring written in ASCII. A non-ASCII one is caught anyway.
SPANISH_MARKERS = {
    "configuracion",
    "configura ",
    "devuelve ",
    "ejecuta ",
    "maneja ",
    "representa ",
    "resuelve ",
}


def _production_files() -> list[Path]:
    """Return every production Python module in the monorepo."""
    return sorted(path for root in PRODUCTION_ROOTS for path in root.glob("*/src/**/*.py"))


def _documented_nodes(tree: ast.AST) -> list[ast.AST]:
    """Return modules, classes, and functions that require documentation."""
    documented_types = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
    return [node for node in ast.walk(tree) if isinstance(node, documented_types)]


def test_the_gate_finds_the_same_modules_from_any_directory(tmp_path, monkeypatch) -> None:
    """ING-1: launched from packages/, the gate saw zero files and passed."""
    from_root = _production_files()
    monkeypatch.chdir(tmp_path)
    assert from_root
    assert _production_files() == from_root


def test_production_callables_have_english_docstrings() -> None:
    """Require an English docstring on every production module and callable."""
    files = _production_files()
    assert files, "no production module found: the gate would pass on nothing"
    failures: list[str] = []
    for path in files:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in _documented_nodes(tree):
            docstring = ast.get_docstring(node)
            name = getattr(node, "name", "<module>")
            line = getattr(node, "lineno", 1)
            if not docstring:
                failures.append(f"{path}:{line}: missing docstring for {name}")
                continue
            lowered = docstring.casefold()
            if not docstring.isascii() or any(word in lowered for word in SPANISH_MARKERS):
                failures.append(f"{path}:{line}: non-English docstring for {name}")
    assert not failures, "\n" + "\n".join(failures)
