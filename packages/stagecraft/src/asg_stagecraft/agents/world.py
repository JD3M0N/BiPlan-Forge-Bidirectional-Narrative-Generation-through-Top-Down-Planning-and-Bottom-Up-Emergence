"""Compact world construction."""

from ..schemas import StoryRequest, WorldArtifact
from .base import Agent, story_specification_header


class WorldBuilderAgent(Agent[WorldArtifact]):
    """Represent WorldBuilderAgent data and behavior."""

    name = "world"

    def run(self, request: StoryRequest) -> WorldArtifact:
        """Run the WorldBuilderAgent workflow."""
        return self.provider.generate_structured(
            system_instruction=(
                "Build a purposeful world scaled to the qualitative narrative profile. Keep "
                "Essential worlds compact. Give Developed stories enough distinct rules, "
                "locations, and objects to support escalating complications and a secondary arc. "
                "Give Expansive stories enough distinct settings and consequential elements to "
                "support the main plot, meaningful subplots, and broad world consequences. Include "
                "only elements that affect choices or consequences. Give locations and objects "
                "stable lowercase IDs. Return artifact content in English."
            ),
            prompt=story_specification_header(request),
            schema=WorldArtifact,
            profile="planning",
        )
