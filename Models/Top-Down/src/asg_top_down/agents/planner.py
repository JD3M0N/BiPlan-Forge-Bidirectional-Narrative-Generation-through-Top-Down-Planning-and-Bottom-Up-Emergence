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
                "Design a causal story plan and a complete TaxonomyApplication in English from the "
                "request and retrieved taxonomy candidates. Select one primary taxonomy. Select at "
                "most one accent only when the candidate has explicit prompt evidence. Choose a small "
                "subset of option IDs: preserve selected reader promises, but treat roles, movements, "
                "complications, twists, and conclusions as a flexible palette that may be merged, "
                "reordered, reinterpreted, or omitted. A twist is never mandatory. The protagonist's "
                "goal, mistaken belief or conviction, active opposition, irreversible choices, climax, "
                "and ending must form one causal argument. All planning text must be English."
            ),
            prompt=(f"NORMALIZED SPECIFICATION:\n{json_text(request.agent_spec())}\n\nBLUEPRINT:\n{json_text(blueprint.model_context())}"
                    f"{repair_feedback}"),
            schema=StoryPlanArtifact,
        )
