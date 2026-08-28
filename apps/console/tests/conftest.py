from pathlib import Path

import pytest
from asg_escape_room import load_room


@pytest.fixture
def maps_dir() -> Path:
    return Path(__file__).parents[3] / "packages" / "escape_room" / "maps"


@pytest.fixture
def room(maps_dir):
    return load_room(maps_dir / "minimal_room.json")
