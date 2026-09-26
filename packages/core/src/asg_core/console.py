"""Console stream setup shared by the command-line entry points."""

from __future__ import annotations

import sys


def use_utf8_output() -> None:
    """Make stdout and stderr write UTF-8, replacing what a legacy console cannot encode."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")
