"""DAG planning and bounded plan refinement."""

from ..profiles import MIN_EVENTS_PER_CHAPTER, profile_chapter_band, profile_event_target
from ..schemas import (
    CharactersArtifact,
    NarrativeBlueprint,
    PlanReview,
    StoryPlanDraft,
    StoryRequest,
    WorldArtifact,
)
from .base import Agent, json_text, story_specification_header


class PlotPlannerAgent(Agent[StoryPlanDraft]):
    """Represent PlotPlannerAgent data and behavior."""

    name = "plot_planner"

    def run(
        self,
        request: StoryRequest,
        world: WorldArtifact,
        characters: CharactersArtifact,
        repair_feedback: str = "",
        plan_review: PlanReview | None = None,
        blueprint: NarrativeBlueprint | None = None,
    ) -> StoryPlanDraft:
        """Run the PlotPlannerAgent workflow."""
        low, high = profile_chapter_band(request.narrative_profile)
        low_events, high_events = profile_event_target(request.narrative_profile)
        return self.provider.generate_structured(
            system_instruction=(
                "Plan a complete story as generic events connected by causal or temporal "
                "dependencies. Do not target or infer word or prose-length budgets. Plan the "
                f"story in {low} to {high} chapters, which is the range this profile normally "
                "needs; leave it only when the material genuinely demands it. Give every chapter "
                f"at least {MIN_EVENTS_PER_CHAPTER} events, which means {low_events} to "
                f"{high_events} events in total for that chapter range. Never plan fewer than "
                f"{low_events} events, never leave a chapter carrying a single event, and never "
                "let one chapter absorb most of the story. "
                "Chapter and event orders must be consecutive from 1. "
                "Dependencies may only point from an earlier event to a later event. Use only "
                "canonical character, location, and object IDs. Build a weakly connected graph "
                "with a causal backbone, while allowing branches and joins. Every event must "
                "change the story state through concrete effects; never inflate the graph by "
                "dividing one unchanged action into multiple events. Expansive plans require one "
                "earlier event with at least two outgoing causal dependencies and a later event "
                "with at least two incoming causal dependencies; independent parallel roots are "
                "not a branch. Worked example of a valid branch and join: event_2 -> event_4 and "
                "event_2 -> event_5 make event_2 the branch, then event_4 -> event_6 and "
                "event_5 -> event_6 make event_6 the join; every edge points forward "
                "(2 < 4, 2 < 5, 4 < 6, 5 < 6) and the branch comes before the join. "
                "PAYOFF_OF CONTRACT: payoff_of may contain only exact PlotEvent IDs "
                "from earlier events, such as event_1. Never put object IDs, character IDs, "
                "location IDs, names, descriptions, or other prose in payoff_of. Use [] when an "
                "event pays off no earlier event. Give every chapter a dramatic goal, state "
                "transition, and turning point. All fields, including the working chapter titles, "
                "must be in English. Use only the fields defined by the response schema."
            ),
            prompt=(
                f"{story_specification_header(request, blueprint)}"
                f"\n\nWORLD:\n{json_text(world)}"
                f"\n\nCHARACTERS:\n{json_text(characters)}"
                f"\n\nPLAN REVIEW TO APPLY:\n{json_text(plan_review) if plan_review else 'none'}"
                f"{repair_feedback}"
            ),
            schema=StoryPlanDraft,
            profile="planning",
        )
