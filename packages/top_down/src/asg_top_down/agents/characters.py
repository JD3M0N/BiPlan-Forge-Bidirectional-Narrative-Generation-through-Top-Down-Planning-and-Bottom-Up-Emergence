"""Compact cast construction."""

from ..schemas import CharactersArtifact, StoryRequest, WorldArtifact
from .base import Agent, json_text, story_specification_header


class CharacterDesignerAgent(Agent[CharactersArtifact]):
    """Represent CharacterDesignerAgent data and behavior."""

    name = "characters"

    def run(self, request: StoryRequest, world: WorldArtifact) -> CharactersArtifact:
        """Run the CharacterDesignerAgent workflow."""
        return self.provider.generate_structured(
            system_instruction=(
                "Create a purposeful cast scaled to the qualitative narrative profile, with stable "
                "lowercase IDs, distinct goals, credible motivations, active conflicts, concise "
                "arcs, and recognizable voices. Keep Essential casts lean. Give Developed stories "
                "supporting characters capable of sustaining a functional secondary arc. Give "
                "Expansive stories multiple interacting arcs capable of sustaining meaningful "
                "subplots. Opposition must pursue a goal incompatible with the protagonist's goal. "
                "Relationships must use canonical character IDs. Do not use scores, sliders, or "
                "hidden planning labels. Return artifact content in English."
            ),
            prompt=(f"{story_specification_header(request)}\n\nWORLD:\n{json_text(world)}"),
            schema=CharactersArtifact,
            profile="planning",
        )
