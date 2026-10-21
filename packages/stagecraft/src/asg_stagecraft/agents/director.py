"""The stage manager: holds the script the actors never see, and keeps the scene moving.

The asymmetry between this agent and the actors is the architecture. The stage manager knows
the beat that must land and the promise the moment owes the reader; the actors know only their
own circumstances. So direction can only ever arrive as a *motivation* - a note that gives a
character a reason - never as a line to say. An actor handed its line recites; an actor handed a
reason plays.

Two guards live here rather than in the prompt. The stage manager is shown its current beat and
the transcript so far, and never a later scene, so it cannot leak a plot turn that has not
happened yet. And when a beat overruns its budget, it closes the beat with something the world
itself does, visibly, on stage - so the log stays the only source of what happened, and a forced
beat is still a beat that was performed rather than asserted.
"""

from ..stage.schemas import (
    BeatCheckDraft,
    BeatDirection,
    FutureConflict,
    FutureRevision,
    TypedBeatCheckDraft,
    WorldEventAssessment,
)
from ..writing.orientation import SPATIAL_RULES
from .base import Agent

_DIRECTION_RULES = (
    "You direct by motivation, never by dictation. A note gives one character a reason to push, "
    "resist, reveal or retreat right now; it never contains a line to be spoken, and it never "
    "tells an actor what another character will do. Name the character each note is for, as "
    "'ana: ...'. Keep every note to one sentence an actor could act on immediately. "
    "You know things the actors do not. Never put a fact into a note that the character it is "
    "addressed to has not learned on stage, and never refer to anything that has not happened "
    "yet."
)


def genre_clause(genre: str) -> str:
    """Point the notes at what the requested genre lives on, or say nothing without one.

    7.12: the navigators run asked for adventure and "a city in the sky", and every scene was
    the crew arguing on deck. The director only gives motives, so this shapes which motive it
    picks; it never adds an event, which SIM-2 keeps out of the director's hands.
    """
    if not genre.strip():
        return ""
    return (
        f" The story is {genre.strip()}: let your notes favour what that genre lives on - action, "
        "danger, discovery, wonder or humour, as it fits - over characters restating an "
        "argument they have already made."
    )


# What each rung of the escalation ladder asks for, on top of reading the clauses. The ladder
# exists because the first real runs deadlocked: the notes set one character pressing and
# another resisting, nobody ever had a reason to cross, and four beats in twelve were closed
# by a thunderclap that resolved nothing - one of them the ending of a mystery.
_MODE_CLAUSES: dict[str, str] = {
    "check": (
        " If a clause is missing, give at most two notes that move the scene towards it, and "
        "name who should move next. Leave turning_actor_id and stage_event empty."
    ),
    "turn": (
        " The characters are holding their positions and the missing clause will not happen "
        "on its own. Name turning_actor_id: the one character whose change it needs - who has "
        "to give ground, confess, discover or decide. Give that character one of your notes, "
        "and make it a reason true to them to change now, in their own way: something they "
        "have just seen or heard on stage, quoted «like this» from the transcript, never the "
        "change itself. Your other note, if any, must not block that change. Leave stage_event "
        "empty."
    ),
    "stall": (
        " The scene has used its time. You may offer a stage_event in {language}: an opportunity "
        "or pressure consistent with established circumstances. Never supply a new solution, "
        "identity, confession, document content or a deduction. Actors must discover and choose. "
        "List world_items for every object affected, with its current holder as actor. "
        "Cite world_basis when drawing on performed evidence. Empty is better than contrivance. "
        "Name turning_actor_id and give a motivation to react, never the desired conclusion."
    ),
    "final": (
        " The world has already stepped in. Only read the clauses; leave the notes, "
        "turning_actor_id and stage_event empty."
    ),
}


# 7.17 (typed_clauses): 11 of the 22 beats forced in the 7.12-7.16 runs were a journey or an
# arrival the actors could not act out ("the ship breaks through into the sea"), and 3 needed
# someone who was not on stage. Tagged, the engine can let the world carry out those clauses.
TYPED_CLAUSES = (
    " Tag every clause with its kind: decision when someone on stage chooses or does it, "
    "revelation when someone on stage tells or discovers a fact, world when it is a journey, an "
    "arrival or anything the world or someone off stage does, which the characters cannot act "
    "out. A fixed clause about a fact is a revelation."
)


class StageManagerAgent(Agent[BeatDirection]):
    """Open each beat, judge whether it has landed, and unstick a scene that has stalled."""

    name = "stage_manager"

    def open_beat(self, context: str, language: str, genre: str = "") -> BeatDirection:
        """Choose who moves first in a beat and give them a reason to."""
        return self.provider.generate_structured(
            system_instruction=(
                "You are the Stage Manager of an improvised performance. The scene below has to "
                f"reach one particular thing happening. The actors speak {language} and are "
                "improvising: they do not know what that thing is, and they must not be told. "
                f"{_DIRECTION_RULES}{genre_clause(genre)} "
                "Choose which character moves first — whoever has the strongest reason to act "
                f"right now — and give at most two notes, written in {language}. Then, for each "
                f"character on stage, restate in {language} what they want right now, from their "
                "objective under EN ESCENA, as something they can play; never add what that "
                "character does not know."
            ),
            prompt=context,
            schema=BeatDirection,
            profile="review",
        )

    def check(
        self,
        context: str,
        language: str,
        *,
        mode: str = "check",
        genre: str = "",
        typed: bool = False,
    ) -> BeatCheckDraft:
        """Read the beat clause by clause, and escalate as far as the mode allows.

        The modes are the rungs of the engine's escalation ladder. "check" only reads and nudges;
        "turn" must also name who has to change and give them a reason; "stall" must also make
        the world deliver the missing clause; "final" only reads. Whether the beat landed is
        never asked for: the engine derives it from the clauses.
        """
        return self.provider.generate_structured(
            system_instruction=(
                "You are the Stage Manager. Read what the actors have performed against the beat "
                "below. Break the beat's outcome into its clauses and judge each one on its own: "
                "shown only if an audience watching this scene would have seen it happen, and "
                "then cite the turn IDs that show it. Judge what was played, not what was meant. "
                "Where the beat takes for granted something the performance never set up - an "
                "object nobody took, a deal nobody made - the performance rules: judge the "
                "change the clause names (someone yields, a group reunites) against what was "
                "played, not the detail that never happened. "
                "A clause that describes a situation rather than an action is shown as soon as "
                "the situation is established on stage. Include each required revelation as "
                "its own exact clause, citing a visible turn that supports its stated method. "
                "Record an established world fact only when a cited action or world turn shows "
                "it directly. For every part supply sources with turn_id, channel "
                "and an exact excerpt. "
                "For every proposed fact supply source and classify it as "
                "established, claim or belief. "
                "A spoken claim, intention or thought is not a world fact. "
                f"Write your clauses and notes in {language}; when the beat lists fixed clauses, "
                "copy each one as given. "
                f"{_DIRECTION_RULES}{genre_clause(genre)}{SPATIAL_RULES}"
                f"{_MODE_CLAUSES[mode].format(language=language)}"
                + (TYPED_CLAUSES if typed else "")
            ),
            prompt=context,
            schema=TypedBeatCheckDraft if typed else BeatCheckDraft,
            profile="review",
        )

    def review_world(self, context: str) -> WorldEventAssessment:
        """Independently check a proposed intervention before it becomes history."""
        return self.provider.generate_structured(
            system_instruction=(
                "Review the proposed world event against the given premise, "
                "rules, circumstances, gates and performed transcript. An "
                "opportunity or pressure may follow established conditions, but "
                "may not invent evidence, documentary contents, a culprit, a "
                "confession, a solution or reveal a future gate. Judge semantic "
                "compatibility; merely naming a source does not establish it. "
                "Explain rejection precisely."
            ),
            prompt=context,
            schema=WorldEventAssessment,
            profile="review",
        )

    def future_conflict(self, context: str) -> FutureConflict:
        """Identify future events made impossible by witnessed, accepted actions."""
        return self.provider.generate_structured(
            system_instruction=(
                "Compare the performed transcript with the remaining events. Report only a "
                "direct contradiction caused by a witnessed action or world event, with the "
                "exact future event IDs and turn IDs as evidence. A character's claim, plan, "
                "thought or lie is not an established fact. Return empty lists if no future "
                "event is made impossible."
            ),
            prompt=context,
            schema=FutureConflict,
            profile="review",
        )

    def revise_future(self, context: str, language: str) -> FutureRevision:
        """Revise unperformed scenes after the actors have changed the story's course."""
        return self.provider.generate_structured(
            system_instruction=(
                "You revise only the listed future scenes of an improvised play. Keep every "
                "scene ID, order, location and cast fixed. Return each remaining scene once, "
                "either kept with revised outcomes and changed actor objectives or omitted. Kept "
                "scenes must retain the same event IDs and order, and may omit events; never "
                "add an event. Revised beats may replace dependencies with "
                "earlier remaining event IDs "
                "and supporting_fact_ids from established accepted facts. Removing any original "
                "dependency requires an established fact that actually "
                "substitutes its prerequisite. "
                "Never treat an unmet event as achieved. Preserve the user's "
                "premise, explicit constraints and world "
                "rules. Treat the performed transcript as irreversible history. Do not force "
                "an originally planned ending when it no longer follows. Write new scene "
                f"settings and changed objectives in {language}. Omit unchanged objectives. "
                "Actors will see only their own "
                "circumstances and objectives, never this revision."
            ),
            prompt=context,
            schema=FutureRevision,
            profile="planning",
        )

    def run(self, context: str, language: str) -> BeatDirection:
        """Open one beat; the abstract Agent contract requires this name."""
        return self.open_beat(context, language)
