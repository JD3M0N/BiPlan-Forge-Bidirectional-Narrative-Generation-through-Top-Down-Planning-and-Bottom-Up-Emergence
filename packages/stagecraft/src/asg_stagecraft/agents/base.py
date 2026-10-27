"""Shared agent infrastructure."""

import json
from abc import ABC, abstractmethod
from typing import Any, Literal

from pydantic import BaseModel

from ..planning.guidance_models import CompositionArtifact
from ..planning.profiles import profile_guidance
from ..planning.skeletons import blueprint_guidance
from ..runtime.provider import LanguageModelProvider
from ..schemas import NarrativeBlueprint, StoryRequest


def json_text(value: Any) -> str:
    """Serialize a value, including nested Pydantic models, as indented UTF-8 JSON for prompts."""

    def convert(item: Any) -> Any:
        """Turn models into plain JSON data, recursing through dicts, lists and tuples."""
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


class Agent[T](ABC):
    """Base of the pipeline agents: a named step that makes one artifact via a provider."""

    name: str

    def __init__(self, provider: LanguageModelProvider) -> None:
        """Keep the provider used for every model call."""
        self.provider = provider

    @abstractmethod
    def run(self, *args: object, **kwargs: object) -> T:
        """Produce the artifact owned by this agent."""
