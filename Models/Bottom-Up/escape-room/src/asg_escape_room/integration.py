"""Adaptadores neutrales para artefactos JSON producidos por Top-Down."""

from copy import deepcopy
from typing import Any, Mapping

from .contracts import RoomConfig


def apply_top_down_artifacts(
    room: RoomConfig,
    world_artifact: Mapping[str, Any],
    characters_artifact: Mapping[str, Any],
) -> RoomConfig:
    """Superpone ambientación y reparto sin importar clases de Top-Down."""
    adapted = deepcopy(room)
    setting = str(world_artifact.get("setting", "")).strip()
    if setting:
        adapted.name = setting
    characters = characters_artifact.get("characters", [])
    for state, source in zip(adapted.agents, characters):
        name = str(source.get("name", "")).strip()
        role = str(source.get("role", "")).strip()
        if name:
            state.id = name
        if role:
            state.role = role
    return RoomConfig.model_validate(adapted.model_dump())

