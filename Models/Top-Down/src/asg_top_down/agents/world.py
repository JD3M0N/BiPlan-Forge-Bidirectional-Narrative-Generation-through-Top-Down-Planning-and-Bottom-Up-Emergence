from .base import Agent, json_text
from ..schemas import StoryPlanArtifact, StoryRequest, TaxonomyBrief, WorldArtifact


class WorldBuilderAgent(Agent[WorldArtifact]):
    name = "world"

    def run(
        self, request: StoryRequest, plan: StoryPlanArtifact,
        taxonomy_brief: TaxonomyBrief | None = None,
    ) -> WorldArtifact:
        return self.provider.generate_structured(
            system_instruction=(
                "Build a compact story world. Every rule and location must constrain a decision, "
                "create an opportunity, or cause a consequence. Give every location and object a stable "
                "lowercase ID. Declare traversable location connections and initial object locations or "
                "owners. Avoid decorative lore. Return all "
                "artifact text in English regardless of the requested fiction language."
            ),
            prompt=(f"NORMALIZED SPECIFICATION:\n{json_text(request.agent_spec())}\n\nPLAN:\n{json_text(plan)}"
                    f"\n\nTAXONOMY BRIEF:\n{json_text(taxonomy_brief) if taxonomy_brief else 'none'}"),
            schema=WorldArtifact,
        )
