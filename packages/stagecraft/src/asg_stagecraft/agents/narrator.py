"""The narrator: writes the story from the log of what was actually performed.

This is the curation step. A performance log is not a story - it is a record of things that
happened, in the order they happened, at the granularity they happened. Turning one into prose
means selecting, compressing and ordering, which is exactly the work a simulation cannot do for
itself and the reason simulation-only story generators produce transcripts rather than fiction.

The contract is one-directional: the log is the only source of events. The narrator may cut,
merge and reorder within a chapter, and may render a thought as interior narration when the
voice allows it, but it may not add a beat the actors never played. Where the plan and the log
disagree, the log wins - because the log is what happened.
"""

from ..formats import NarrativeVoice
from ..schemas import ChapterPlan, StoryRequest
from .base import Agent, json_text

_VOICE_CLAUSES: dict[NarrativeVoice, str] = {
    NarrativeVoice.OMNISCIENT: (
        "Narrate in the third person, past tense, with access to the inner life of every "
        "character whose thoughts the log records. Move between them when it serves the scene, "
        "but never within a single paragraph."
    ),
    NarrativeVoice.FOCALIZED: (
        "Narrate in the third person, past tense, staying inside one character per scene: the "
        "one whose thoughts the log gives you there. Everyone else is known only by what they "
        "say and do, so render their motives as the focal character reads them, which may be "
        "wrong."
    ),
    NarrativeVoice.FIRST_PERSON: (
        "Narrate in the first person, past tense, as the character whose log this is. You know "
        "only what you witnessed and what you were told. Never report what another character "
        "thought or did out of your sight; if you refer to it at all, refer to it as something "
        "you later learned or still do not know."
    ),
    NarrativeVoice.LIMITED: (
        "Narrate in the third person, past tense, from inside one character only: the one whose "
        "log this is. The narration knows only what they witnessed and what they were told. "
        "Never report what another character thought or did out of their sight. Everyone else "
        "is known only by what they say and do, so render their motives as the point-of-view "
        "character reads them, which may be wrong."
    ),
}

# Who the story is told from, for the voices that are told from one character. First person
# keeps the exact sentence it had before 7.3, so its prompts did not change.
_NARRATOR_CLAUSES: dict[NarrativeVoice, str] = {
    NarrativeVoice.FIRST_PERSON: " You are narrating as {name}.",
    NarrativeVoice.LIMITED: " The point-of-view character is {name}.",
}


def narrator_clause(voice: NarrativeVoice, narrator_name: str) -> str:
    """Name the point-of-view character, for a voice told from one, or return nothing."""
    template = _NARRATOR_CLAUSES.get(voice)
    return template.format(name=narrator_name) if template and narrator_name else ""


def tone_clause(tone: str) -> str:
    """Carry the register the author asked for, or nothing, so a run without one is unchanged.

    The tone arrives in the author's own words and language. It may colour the voice; it may
    never add an event, which the rest of the instruction already forbids.
    """
    if not tone.strip():
        return ""
    return (
        " Write in the register the author asked for, in the fiction's language, and let it "
        f"shape the voice only, never the events: {tone.strip()}."
    )


class NarratorAgent(Agent[str]):
    """Write one chapter of prose from the turns its scenes actually produced."""

    name = "narrator"

    def run(
        self,
        request: StoryRequest,
        chapter: ChapterPlan,
        chapter_title: str,
        voice: NarrativeVoice,
        log: str,
        narrator_name: str = "",
        retry_feedback: str = "",
        tone: str = "",
    ) -> str:
        """Narrate one chapter, inventing nothing the performance did not stage."""
        stable_context = {
            "premise": request.premise,
            "constraints": request.constraints,
            "genre": request.genre,
        }
        return self.provider.generate_text(
            system_instruction=(
                "You are the Narrator. What follows is the record of a performance: what the "
                "characters actually said, did and thought, in the order it happened. Turn it "
                f"into one chapter of finished prose in {request.language}, with no heading and "
                "no process notes. "
                f"{_VOICE_CLAUSES[voice]}{narrator_clause(voice, narrator_name)}"
                f"{tone_clause(tone)} "
                "The log is your only source of events. You may cut what does not earn its "
                "place, merge exchanges, compress time between them and choose where to begin "
                "and end — that selection is your work. You may not invent an event, a line or "
                "a revelation the log does not contain, and where the log and any plan disagree, "
                "the log is what happened. "
                "Curate, do not transcribe: the finished chapter should be shorter than the log. "
                "Moments marked [clave] are the ones the chapter turns on; play those in full, "
                "as scene. Compress everything else - a standoff where both sides repeat their "
                "position, a gesture made again - into a sentence or cut it. Render a recorded "
                "thought only where it changes what the reader understands, and never attach a "
                "thought to every line or gesture. A line in parentheses with no speaker is "
                "something the world did: tell it in the narration's own tense, like everything "
                "else. "
                "Write it as scene, not as summary: keep the spoken exchanges as dialogue under "
                "the dialogue-dash convention of the language, give each beat its own paragraph, "
                "and let what characters do carry what they feel. Hold this through the last "
                "chapter: an ending is a scene, not an account of how matters turned out. "
                "If a question remains open in the log, leave it open. Do not expose "
                "internal IDs, turn identifiers or planning terminology."
            ),
            prompt=(
                "PREMISA Y REGLAS (son contexto, no sucesos ya ocurridos):\n"
                f"{json_text(stable_context)}"
                f"\n\nCHAPTER: {chapter_title}" + f"\n\nPERFORMANCE LOG:\n{log}" + retry_feedback
            ),
            profile="prose",
        )
