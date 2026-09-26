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
from .base import Agent, json_text, story_specification_header

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
}


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
        previous_chapter: str,
        narrator_name: str = "",
        promise_brief: str = "",
        retry_feedback: str = "",
    ) -> str:
        """Narrate one chapter, inventing nothing the performance did not stage."""
        narrator_clause = (
            f" You are narrating as {narrator_name}."
            if narrator_name and voice is NarrativeVoice.FIRST_PERSON
            else ""
        )
        intent = {
            "dramatic_goal": chapter.dramatic_goal,
            "opening_state": chapter.opening_state,
            "turning_point": chapter.turning_point,
            "closing_state": chapter.closing_state,
        }
        return self.provider.generate_text(
            system_instruction=(
                "You are the Narrator. What follows is the record of a performance: what the "
                "characters actually said, did and thought, in the order it happened. Turn it "
                f"into one chapter of finished prose in {request.language}, with no heading and "
                "no process notes. "
                f"{_VOICE_CLAUSES[voice]}{narrator_clause} "
                "The log is your only source of events. You may cut what does not earn its "
                "place, merge exchanges, compress time between them and choose where to begin "
                "and end — that selection is your work. You may not invent an event, a line or "
                "a revelation the log does not contain, and where the log and any plan disagree, "
                "the log is what happened. "
                "Write it as scene, not as summary: keep the spoken exchanges as dialogue under "
                "the dialogue-dash convention of the language, give each beat its own paragraph, "
                "and let what characters do carry what they feel. Hold this through the last "
                "chapter: an ending is a scene, not an account of how matters turned out. "
                "When PROMISE OBLIGATIONS are supplied, deliver each one through what happens "
                "and what is said, never by announcing it. Do not expose internal IDs, turn "
                "identifiers or planning terminology."
            ),
            prompt=(
                f"{story_specification_header(request)}"
                f"\n\nCHAPTER: {chapter_title}"
                f"\n\nWHAT THIS CHAPTER IS FOR:\n{json_text(intent)}"
                + (f"\n\nPROMISE OBLIGATIONS:\n{promise_brief}" if promise_brief else "")
                + f"\n\nPREVIOUS CHAPTER:\n{previous_chapter or 'none'}"
                + f"\n\nPERFORMANCE LOG:\n{log}"
                + retry_feedback
            ),
            profile="prose",
        )
