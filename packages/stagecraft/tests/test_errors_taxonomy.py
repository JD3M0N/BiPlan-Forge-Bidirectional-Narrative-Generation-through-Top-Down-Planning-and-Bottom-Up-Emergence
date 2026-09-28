"""Guard the error taxonomy against classes no production code ever uses."""

import re
from pathlib import Path

from asg_stagecraft.runtime import errors as errors_module

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
ERRORS_MODULE = Path(errors_module.__file__).resolve()
PRODUCTION_GLOBS = ("packages/*/src/**/*.py", "apps/*/src/**/*.py")


def _production_sources() -> list[Path]:
    """Collect every production module except the taxonomy's own definition site."""
    found = [path for glob in PRODUCTION_GLOBS for path in REPOSITORY_ROOT.glob(glob)]
    return [path for path in found if path.resolve() != ERRORS_MODULE]


def _declared_error_names() -> list[str]:
    """Read the class names the taxonomy declares, in declaration order."""
    source = ERRORS_MODULE.read_text(encoding="utf-8")
    return re.findall(r"^class (\w+)\(", source, re.MULTILINE)


def test_every_declared_error_is_used_by_production_code() -> None:
    """An error nothing raises, catches, or classifies is taxonomy that carries no weight."""
    assert (REPOSITORY_ROOT / "packages").is_dir()
    assert (REPOSITORY_ROOT / "apps").is_dir()
    sources = _production_sources()
    names = _declared_error_names()
    assert len(sources) > 1
    assert len(names) > 1
    blob = "\n".join(path.read_text(encoding="utf-8") for path in sources)
    unused = [name for name in names if not re.search(rf"\b{name}\b", blob)]
    assert not unused, "these errors are declared but never used outside errors.py: " + ", ".join(
        unused
    )
