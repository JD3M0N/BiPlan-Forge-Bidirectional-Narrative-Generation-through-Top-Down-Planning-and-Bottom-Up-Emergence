"""DAG planning and bounded plan refinement."""

from ..schemas import (
    CharactersArtifact,
    PlanReview,
    StoryPlanDraft,
    StoryRequest,
    WorldArtifact,
)
from .base import Agent, json_text


class PlotPlannerAgent(Agent[StoryPlanDraft]):
    """Represent PlotPlannerAgent data and behavior."""

    name = "plot_planner"

    def run(
        self,
        request: StoryRequest,
        world: WorldArtifact,
        characters: CharactersArtifact,
        event_budgets: list[int],
        repair_feedback: str = "",
        plan_review: PlanReview | None = None,
    ) -> StoryPlanDraft:
        """Run the PlotPlannerAgent workflow."""
        return self.provider.generate_structured(
            system_instruction=(
                "Plan a complete story as generic events connected by causal or temporal dependencies. "
                "Create exactly the requested number of chapters and exactly the event count assigned to "
                "each chapter. "
                "Chapter and event orders must be consecutive from 1. Dependencies may only point from an "
                "earlier event to a later event. Use only canonical character, location, and object IDs. "
                "Build a weakly connected graph with a causal backbone, while allowing branches and joins. "
                "Every event must change the story state through concrete effects. PAYOFF_OF CONTRACT: "
                "payoff_of may contain only exact PlotEvent IDs from earlier events, such as event_1. Never "
                "put object IDs, character IDs, location IDs, names, descriptions, or other prose in "
                "payoff_of. Use [] when an event pays off no earlier event. Give every chapter a dramatic "
                "goal, state transition, "
                "and turning point. All fields, including the working chapter titles, must be in English. "
                "Use only the fields defined by the response schema."
            ),
            prompt=(
                f"STORY SPECIFICATION:\n{json_text(request.agent_spec())}"
                f"\n\nEXACT EVENT COUNTS BY CHAPTER ORDER: {json_text(event_budgets)}"
                f"\n\nWORLD:\n{json_text(world)}"
                f"\n\nCHARACTERS:\n{json_text(characters)}"
                f"\n\nPLAN REVIEW TO APPLY:\n{json_text(plan_review) if plan_review else 'none'}"
                f"{repair_feedback}"
            ),
            schema=StoryPlanDraft,
        )
