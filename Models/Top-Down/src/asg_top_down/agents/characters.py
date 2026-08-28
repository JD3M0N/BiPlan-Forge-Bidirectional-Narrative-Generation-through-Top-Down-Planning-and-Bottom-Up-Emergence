"""Compact cast construction."""

from .base import Agent, json_text
from ..schemas import CharactersArtifact, StoryRequest, WorldArtifact


class CharacterDesignerAgent(Agent[CharactersArtifact]):
    name = "characters"

    def run(self, request: StoryRequest, world: WorldArtifact) -> CharactersArtifact:
        return self.provider.generate_structured(
            system_instruction=(
                "Create a compact cast with stable lowercase IDs, distinct goals, credible motivations, "
                "active conflicts, concise arcs, and recognizable voices. Opposition must pursue a goal "
                "incompatible with the protagonist's goal. Relationships must use canonical character IDs. "
                "Do not use scores, sliders, or hidden planning labels. Return artifact "
                "content in English."
            ),
            prompt=(
                f"STORY SPECIFICATION:\n{json_text(request.agent_spec())}"
                f"\n\nWORLD:\n{json_text(world)}"
            ),
            schema=CharactersArtifact,
        )
