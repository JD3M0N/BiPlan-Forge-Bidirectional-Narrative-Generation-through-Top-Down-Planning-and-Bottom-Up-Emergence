"""Carga y validación de habitaciones."""

import json
from pathlib import Path

from .contracts import RoomConfig


def load_room(path: str | Path) -> RoomConfig:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return RoomConfig.model_validate(data)

