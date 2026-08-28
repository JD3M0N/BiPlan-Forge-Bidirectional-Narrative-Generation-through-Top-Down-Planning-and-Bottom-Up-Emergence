import json

import pytest
from asg_escape_room.contracts import RoomConfig
from pydantic import ValidationError


def test_loads_valid_room(room) -> None:
    assert room.width == 7
    assert len(room.agents) == 2


def test_rejects_position_outside_map(room) -> None:
    data = room.model_dump(mode="json")
    data["objects"][0]["position"] = [99, 99]
    with pytest.raises(ValidationError, match="dentro del mapa"):
        RoomConfig.model_validate(data)


def test_rejects_duplicate_identifiers(room) -> None:
    data = room.model_dump(mode="json")
    data["objects"][0]["id"] = data["agents"][0]["id"]
    with pytest.raises(ValidationError, match="únicos"):
        RoomConfig.model_validate(data)


def test_rejects_cyclic_puzzles(room) -> None:
    data = room.model_dump(mode="json")
    data["puzzles"][0]["requires"].append("inspect_painting")
    with pytest.raises(ValidationError, match="ciclo"):
        RoomConfig.model_validate(data)


def test_map_is_plain_json(maps_dir) -> None:
    data = json.loads((maps_dir / "escape_room.json").read_text(encoding="utf-8"))
    assert data["name"]
