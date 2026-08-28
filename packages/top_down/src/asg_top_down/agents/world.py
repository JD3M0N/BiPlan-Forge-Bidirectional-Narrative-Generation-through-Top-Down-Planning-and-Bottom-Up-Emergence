"""Compact world construction."""

from ..schemas import StoryRequest, WorldArtifact
from .base import Agent, json_text


class WorldBuilderAgent(Agent[WorldArtifact]):
    """Represent WorldBuilderAgent data and behavior."""

    name = "world"

    def run(self, request: StoryRequest) -> WorldArtifact:
        """Run the WorldBuilderAgent workflow."""
        return self.provider.generate_structured(
            system_instruction=(
                "Build a compact world that supports the premise and conflict. Include only rules, "
                "locations, and objects that affect choices or consequences. Give locations and objects "
                "stable lowercase IDs. Return artifact content in English."
            ),
            prompt=f"STORY SPECIFICATION:\n{json_text(request.agent_spec())}",
            schema=WorldArtifact,
        )
