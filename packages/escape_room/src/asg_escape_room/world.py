"""Load and validate escape-room configurations."""

import json
from pathlib import Path

from .contracts import RoomConfig


def load_room(path: str | Path) -> RoomConfig:
    """Load room."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return RoomConfig.model_validate(data)
