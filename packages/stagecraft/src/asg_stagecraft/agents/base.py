"""Shared agent infrastructure."""

import json
from abc import ABC, abstractmethod
from typing import Any, Generic, Literal, TypeVar

from pydantic import BaseModel

from ..planning.guidance_models import CompositionArtifact
from ..planning.profiles import profile_guidance
from ..planning.skeletons import blueprint_guidance
from ..runtime.provider import LanguageModelProvider
from ..schemas import NarrativeBlueprint, StoryRequest

T = TypeVar("T")


def json_text(value: Any) -> str:
    """Handle the json text operation for component."""

    def convert(item: Any) -> Any:
        """Handle the convert operation for component."""
        if isinstance(item, BaseModel):
            return item.model_dump(mode="json")
        if isinstance(item, dict):
            return {key: convert(child) for key, child in item.items()}
        if isinstance(item, (list, tuple)):
            return [convert(child) for child in item]
        return item

    return json.dumps(convert(value), ensure_ascii=False, indent=2)


def story_specification_header(
    request: StoryRequest,
    blueprint: NarrativeBlueprint | CompositionArtifact | None = None,
    *,
    audience: Literal["characters", "planning"] = "planning",
) -> str:
    """Return the shared STORY SPECIFICATION + NARRATIVE PROFILE CONTRACT header."""
    header = (
        f"STORY SPECIFICATION:\n{json_text(request.agent_spec())}"
        f"\n\nNARRATIVE PROFILE CONTRACT:\n{profile_guidance(request.narrative_profile)}"
    )
    if blueprint is None:
        return header
    if isinstance(blueprint, CompositionArtifact):
        block = blueprint.character_block if audience == "characters" else blueprint.planning_block
        return f"{header}\n\n{block}" if block else header
    return f"{header}\n\n{blueprint_guidance(blueprint)}"


class Agent(ABC, Generic[T]):
    """Represent Agent data and behavior."""

    name: str

    def __init__(self, provider: LanguageModelProvider) -> None:
        """Initialize the Agent instance."""
        self.provider = provider

    @abstractmethod
    def run(self, *args: object, **kwargs: object) -> T:
        """Produce the artifact owned by this agent."""
