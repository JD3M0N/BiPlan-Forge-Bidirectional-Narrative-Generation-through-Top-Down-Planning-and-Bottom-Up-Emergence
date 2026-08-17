from .base import Agent, json_text
from ..schemas import StoryPlanArtifact, StoryRequest, WorldArtifact


class WorldBuilderAgent(Agent[WorldArtifact]):
    name = "world"

    def run(self, request: StoryRequest, plan: StoryPlanArtifact) -> WorldArtifact:
        return self.provider.generate_structured(
            system_instruction=(
                "Build a compact story world. Every rule and location must constrain a decision, "
                "create an opportunity, or cause a consequence. Avoid decorative lore."
            ),
            prompt=f"REQUEST:\n{json_text(request)}\n\nPLAN:\n{json_text(plan)}",
            schema=WorldArtifact,
        )
