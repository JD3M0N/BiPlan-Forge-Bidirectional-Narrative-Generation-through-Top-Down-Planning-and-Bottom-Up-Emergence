"""Enforce concise English documentation across production Python code."""

from __future__ import annotations

import ast
from pathlib import Path

PRODUCTION_ROOTS = (Path("packages"), Path("apps"))
SPANISH_MARKERS = {
    "configuraci?n",
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


def test_production_callables_have_english_docstrings() -> None:
    """Require an English docstring on every production module and callable."""
    failures: list[str] = []
    for path in _production_files():
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
