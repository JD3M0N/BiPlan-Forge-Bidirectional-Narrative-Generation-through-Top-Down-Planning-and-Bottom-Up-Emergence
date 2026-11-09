"""The asg-latex command: build the thesis PDF in a scratch copy of redaccion/.

Successive latexmk passes inside redaccion/tesis on drive E: reread Thesis.aux with
leftovers of the previous pass and fail with "Extra }" or "File ended while scanning".
Building in a mirror under the system temporary directory avoids it, so this command
mirrors redaccion/, runs latexmk there and copies the PDF and its log back.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from .console import use_utf8_output
from .paths import find_project_root

MAIN = "Thesis"
# Folders that never take part in the build: slides and local leftovers.
SKIPPED_DIRS = frozenset({"presentaciones", "build", "__pycache__"})
# latexmk outputs: never mirrored, so the build keeps its own and the source never wins.
ARTIFACT_ENDINGS = (
    ".aux",
    ".bbl",
    ".bcf",
    ".blg",
    ".fdb_latexmk",
    ".fls",
    ".lof",
    ".log",
    ".lot",
    ".nlo",
    ".out",
    ".run.xml",
    ".synctex.gz",
    ".toc",
    "-SAVE-ERROR",
)
COPIED_BACK = tuple(f"{MAIN}{suffix}" for suffix in (".pdf", ".log", ".toc", ".lof", ".lot"))


def is_artifact(name: str) -> bool:
    """Tell whether a file name is a LaTeX build output rather than a source."""
    return name == f"{MAIN}.pdf" or name.endswith(ARTIFACT_ENDINGS)


def _sources(root: Path) -> set[Path]:
    """List the source files below root, relative to it, skipping outputs and slides."""
    found = set()
    for folder, dirs, files in os.walk(root):
        dirs[:] = [name for name in dirs if name not in SKIPPED_DIRS]
        base = Path(folder).relative_to(root)
        found.update(base / name for name in files if not is_artifact(name))
    return found


def mirror(source: Path, target: Path) -> int:
    """Make target hold the sources of source; return how many files were copied.

    Unchanged files keep their timestamps, so latexmk only reruns what changed. Sources
    deleted from source are deleted from target too, while build outputs in target stay.
    """
    wanted = _sources(source)
    copied = 0
    for relative in sorted(wanted):
        origin, destination = source / relative, target / relative
        if destination.exists():
            have, want = destination.stat(), origin.stat()
            if have.st_size == want.st_size and int(have.st_mtime) == int(want.st_mtime):
                continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(origin, destination)
        copied += 1
    if target.exists():
        for stale in _sources(target) - wanted:
            (target / stale).unlink()
    return copied


@dataclass(frozen=True)
class LogSummary:
    """What the final pass of a LaTeX log says about the PDF."""

    pages: int | None
    errors: tuple[str, ...]
    undefined: int
    overfull: int


def summarize(log: str) -> LogSummary:
    """Read the page count, errors, undefined references and overfull boxes of a log."""
    pages = re.search(r"Output written on \S+ \((\d+) pages?", log)
    return LogSummary(
        pages=int(pages.group(1)) if pages else None,
        errors=tuple(re.findall(r"^! (.+)$", log, re.M)),
        # Both warnings exist only for undefined keys; the log wraps lines at 79 columns,
        # so the word "undefined" itself may land on the next line.
        undefined=len(re.findall(r"LaTeX Warning: (?:Reference|Citation) `", log)),
        overfull=len(re.findall(r"^Overfull \\hbox", log, re.M)),
    )


Runner = Callable[..., subprocess.CompletedProcess]


def build(
    source: Path, build_dir: Path, latexmk: str, *, run: Runner = subprocess.run
) -> tuple[int, LogSummary | None]:
    """Mirror source into build_dir, run latexmk there and copy the results back.

    Returns latexmk's exit code and the summary of its log. The PDF only comes back when
    latexmk succeeded, so a failed build never replaces a good PDF; the log always does.
    """
    copy = build_dir / source.name
    copied = mirror(source, copy)
    print(f"Copia en {copy}: {copied} archivos actualizados.")
    workdir = copy / "tesis"
    result = run([latexmk, "-silent", f"{MAIN}.tex"], cwd=workdir, check=False)
    for name in COPIED_BACK:
        built = workdir / name
        if built.exists() and (result.returncode == 0 or name.endswith(".log")):
            shutil.copy2(built, source / "tesis" / name)
    log = workdir / f"{MAIN}.log"
    if not log.exists():
        return result.returncode, None
    return result.returncode, summarize(log.read_text(encoding="utf-8", errors="replace"))


def parser() -> argparse.ArgumentParser:
    """Build the asg-latex argument parser."""
    result = argparse.ArgumentParser(
        prog="asg-latex",
        description="Compila la tesis (redaccion/tesis/Thesis.tex) en una copia temporal y "
        "deja Thesis.pdf y su log en redaccion/tesis/.",
    )
    result.add_argument(
        "--source", type=Path, help="carpeta redaccion/ (por defecto, la del repositorio)"
    )
    result.add_argument(
        "--build",
        type=Path,
        default=Path(tempfile.gettempdir()) / "tesis-build",
        help="carpeta de la copia (por defecto, %%TEMP%%/tesis-build)",
    )
    result.add_argument("--clean", action="store_true", help="borra la copia y compila desde cero")
    return result


def main(argv: list[str] | None = None) -> int:
    """Compile the thesis and report pages, errors, undefined references and overfull boxes."""
    use_utf8_output()
    args = parser().parse_args(argv)
    source = (args.source or find_project_root() / "redaccion").resolve()
    if not (source / "tesis" / f"{MAIN}.tex").is_file():
        print(f"No se encuentra {source / 'tesis' / (MAIN + '.tex')}.")
        return 2
    latexmk = shutil.which("latexmk")
    if latexmk is None:
        print("No se encuentra latexmk: instala MiKTeX o TeX Live y añádelo al PATH.")
        return 2
    if args.clean and args.build.exists():
        shutil.rmtree(args.build)
    code, summary = build(source, args.build.resolve(), latexmk)
    if summary is None:
        print(f"latexmk terminó con {code} y no dejó {MAIN}.log.")
        return 1
    for error in summary.errors:
        print(f"Error: {error}")
    pages = summary.pages if summary.pages is not None else "sin"
    print(
        f"{pages} páginas, {summary.undefined} referencias o citas indefinidas, "
        f"{summary.overfull} cajas desbordadas."
    )
    if code != 0 or summary.errors:
        print(f"Falló la compilación: revisa {source / 'tesis' / (MAIN + '.log')}.")
        return 1
    print(f"PDF en {source / 'tesis' / (MAIN + '.pdf')}.")
    return 0
