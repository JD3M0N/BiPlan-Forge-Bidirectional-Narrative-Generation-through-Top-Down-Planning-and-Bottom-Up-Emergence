"""Promise-Progress-Payoff ledger drawn over a plan that is already frozen."""

from ..profiles import promise_aim, promise_band
from ..promise_brief import event_index
from ..schemas import PromiseLedgerDraft, StoryPlan, StoryRequest
from .base import Agent, json_text, story_specification_header


class PromiseLedgerAgent(Agent[PromiseLedgerDraft]):
    """Read the validated plan and state what the story owes its reader."""

    name = "promise_ledger"

    def run(
        self,
        request: StoryRequest,
        plan: StoryPlan,
        repair_feedback: str = "",
    ) -> PromiseLedgerDraft:
        """Draw the promise ledger of one validated plan without altering the plan."""
        low, high = promise_band(request.narrative_profile)
        aim = promise_aim(request.narrative_profile)
        return self.provider.generate_structured(
            system_instruction=(
                "You are the Promise Architect. The validated STORYLINE below is frozen. Design a "
                "Promise-Progress-Payoff ledger over it. Never request, imply, or invent an "
                "event: every opening, progress and payoff must cite the id of an event the plan "
                "already contains, and a ledger citing anything else is sent back. You are not "
                "changing what happens; you are stating what the reader is made to expect while "
                "it happens. "
                "A promise is an expectation the opening of the story establishes. Promises come "
                "in four flavors: story_direction, the big question the story answers; "
                "character_conflict, what the protagonist wants and what stands in the way; "
                "genre_structure, the convention the story signals it will honor; and tone, the "
                "register the reader is taught to expect. Exactly one promise is the primary "
                "one, it is the story_direction promise, and it pays off in the final chapter. "
                f"Open between {low} and {high} promises, aiming at {aim}: every promise you open "
                "must be paid, so promising more than the ending has room to answer is worse than "
                "promising less. "
                "Progress is the signposted movement toward a promise, and how you signpost "
                "depends on the promise: reveal a clue or eliminate a suspect for a mystery, "
                "close the distance or uncover more of the map for a quest, show the character "
                "beating something they could not beat before for a competence promise, catch "
                "them making a choice they would not have made at the start for a transformation. "
                "Each progress must name what visibly changes and what new cost or information "
                "that change brings. A middle where nothing signposts is the most common reason a "
                "reader stops. "
                "A payoff is a surprising but fulfilling answer to its promise. It must cost the "
                "characters something, it must be prepared by progresses of its own promise, and "
                "it must not be reached by breaking what was promised in order to surprise. "
                "Anchor each beat where the plan already puts that material: an opening on an "
                "early event, progresses between opening and payoff, the payoff last. Write every "
                "field in English, concretely, naming characters and objects as the plan names "
                "them. Use only the fields defined by the response schema."
            ),
            prompt=(
                f"{story_specification_header(request)}"
                f"\n\nVALIDATED PLAN:\n{json_text(plan)}"
                f"\n\nEVENT INDEX, the only ids a beat may anchor to:\n{event_index(plan)}"
                f"{repair_feedback}"
            ),
            schema=PromiseLedgerDraft,
            profile="planning",
        )
