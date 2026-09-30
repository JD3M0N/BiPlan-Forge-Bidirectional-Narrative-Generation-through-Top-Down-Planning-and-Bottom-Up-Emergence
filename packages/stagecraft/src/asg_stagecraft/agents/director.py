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

from ..stage.schemas import BeatCheckDraft, BeatDirection, FutureConflict, FutureRevision
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
        "and make it a reason true to them to change now, in their own way. Your other note, "
        "if any, must not block that change. Leave stage_event empty."
    ),
    "stall": (
        " The scene has used its time. Supply a stage_event in {language}: something the world "
        "itself does, which everyone present sees or hears, that makes the missing clause "
        "happen or impossible to deny - a piece of evidence surfaces, someone arrives, a door "
        "gives way. It must deliver the missing clause, not set a mood: never weather, light or "
        "a sound that changes nothing, and never a device listed under EVENTOS DEL MUNDO YA "
        "USADOS. Still name turning_actor_id and give them a note: they react first."
    ),
    "final": (
        " The world has already stepped in. Only read the clauses; leave the notes, "
        "turning_actor_id and stage_event empty."
    ),
}


class StageManagerAgent(Agent[BeatDirection]):
    """Open each beat, judge whether it has landed, and unstick a scene that has stalled."""

    name = "stage_manager"

    def open_beat(self, context: str, language: str) -> BeatDirection:
        """Choose who moves first in a beat and give them a reason to."""
        return self.provider.generate_structured(
            system_instruction=(
                "You are the Stage Manager of an improvised performance. The scene below has to "
                f"reach one particular thing happening. The actors speak {language} and are "
                "improvising: they do not know what that thing is, and they must not be told. "
                f"{_DIRECTION_RULES} "
                "Choose which character moves first — whoever has the strongest reason to act "
                "right now — and give at most two notes."
            ),
            prompt=context,
            schema=BeatDirection,
            profile="review",
        )

    def check(self, context: str, language: str, *, mode: str = "check") -> BeatCheckDraft:
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
                "A clause that describes a situation rather than an action is shown as soon as "
                "the situation is established on stage. Include each required revelation as "
                "its own exact clause, citing a visible turn that supports its stated method. "
                "Record an established world fact only when a cited action or world turn shows "
                "it directly. A spoken claim, intention or thought is not a world fact. "
                f"{_DIRECTION_RULES}"
                f"{_MODE_CLAUSES[mode].format(language=language)}"
            ),
            prompt=context,
            schema=BeatCheckDraft,
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
                "add an event. Preserve the user's premise, explicit constraints and world "
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
