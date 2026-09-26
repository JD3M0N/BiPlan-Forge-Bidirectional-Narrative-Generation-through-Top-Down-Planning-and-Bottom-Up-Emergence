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

from ..stage.schemas import BeatCheckDraft, BeatDirection
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

    def check(self, context: str, language: str, *, stalled: bool = False) -> BeatCheckDraft:
        """Judge whether the beat has actually happened, and say what to do about it."""
        stall_clause = (
            " This scene has run long without reaching its beat. Supply a stage_event: something "
            "the world itself does that everyone present can see or hear, written in "
            f"{language}, which forces the situation to move. Not a character's action, and not "
            "narration: a knock, a light failing, someone arriving, a sound from the next room."
            if stalled
            else " Leave stage_event empty unless the scene has genuinely stopped moving."
        )
        return self.provider.generate_structured(
            system_instruction=(
                "You are the Stage Manager. Read what the actors have performed and decide "
                "whether the beat below has actually happened on stage. Judge what was played, "
                "not what was intended: a beat is reached only when an audience watching this "
                "scene would have seen it happen. If it has, cite the turn IDs that show it. If "
                "it has not, say in one line what still has to occur, and name who should move "
                f"next. {_DIRECTION_RULES}{stall_clause}"
            ),
            prompt=context,
            schema=BeatCheckDraft,
            profile="review",
        )

    def run(self, context: str, language: str) -> BeatDirection:
        """Open one beat; the abstract Agent contract requires this name."""
        return self.open_beat(context, language)
