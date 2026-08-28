"""One-shot planning of chapters and generic events."""

from .base import Agent, json_text
from ..schemas import CharactersArtifact, StoryPlanDraft, StoryRequest, WorldArtifact


class PlotPlannerAgent(Agent[StoryPlanDraft]):
    name = "plot_planner"

    def run(
        self,
        request: StoryRequest,
        world: WorldArtifact,
        characters: CharactersArtifact,
        chapter_count: int,
        repair_feedback: str = "",
    ) -> StoryPlanDraft:
        return self.provider.generate_structured(
            system_instruction=(
                "Plan a complete story as generic events connected by causal or temporal dependencies. "
                "Create exactly the requested number of chapters and at least one event in every chapter. "
                "Chapter and event orders must be consecutive from 1. Dependencies may only point from an "
                "earlier event to a later event. Use only canonical character, location, and object IDs. "
                "Keep the graph purposeful but do not force every event into a single chain. Chapter titles "
                "must use the requested fiction language; all other planning text must be English. Use "
                "only the generic event and dependency fields defined by the response schema."
            ),
            prompt=(
                f"STORY SPECIFICATION:\n{json_text(request.agent_spec())}"
                f"\n\nREQUIRED CHAPTER COUNT: {chapter_count}"
                f"\n\nWORLD:\n{json_text(world)}"
                f"\n\nCHARACTERS:\n{json_text(characters)}"
                f"{repair_feedback}"
            ),
            schema=StoryPlanDraft,
        )
