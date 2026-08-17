from .base import Agent, json_text
from ..narrative_db import NarrativeBlueprint
from ..schemas import StoryPlanArtifact, StoryRequest


class PlannerAgent(Agent[StoryPlanArtifact]):
    name = "planner"

    def run(
        self, request: StoryRequest, blueprint: NarrativeBlueprint,
        repair_feedback: str = "",
    ) -> StoryPlanArtifact:
        return self.provider.generate_structured(
            system_instruction=(
                "Design a causal story plan from the request and retrieved narrative knowledge. "
                "Choose a small compatible composition rather than stacking labels. The protagonist's "
                "goal, mistaken belief or conviction, active opposition, irreversible choices, climax, "
                "and ending must form one causal argument. Use catalog IDs only in archetype fields."
            ),
            prompt=(f"REQUEST:\n{json_text(request)}\n\nBLUEPRINT:\n{json_text(blueprint)}"
                    f"{repair_feedback}"),
            schema=StoryPlanArtifact,
        )
