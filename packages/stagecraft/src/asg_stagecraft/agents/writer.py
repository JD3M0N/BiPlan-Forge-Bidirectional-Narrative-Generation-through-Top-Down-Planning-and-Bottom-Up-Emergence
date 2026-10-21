"""First-draft generation and note-driven chapter editing."""

from ..schemas import (
    ChapterPlan,
    CharacterProfile,
    PlotEvent,
    RevisionNote,
    SceneCard,
    StoryPlan,
    StoryPresentation,
    StoryRequest,
    WorldArtifact,
)
from ..writing.chapter_edits import ParagraphEdits, edit_request
from ..writing.orientation import ORIENTATION_RULES
from .base import Agent, json_text, story_specification_header
from .style import style_clause

# How a chapter is written from its scene cards (7.17, the scene_cards option).
SCENE_CARD_CLAUSE = (
    " Write the chapter scene by scene from the SCENE CARDS, in their order, one card per scene: "
    "open where the card places it, let each character go after what they want, make the first "
    "attempt fail on the obstacle, land the turn, use the sensory detail once, leave what is "
    "unsaid unsaid, and end the scene on its closing. Move between scenes with one sentence of "
    "place or time; briefly summarize an established transfer when needed for orientation."
)


class DrafterAgent(Agent[str]):
    """Create localized titles and the first prose draft."""

    name = "drafter"

    def presentation(self, request: StoryRequest, plan: StoryPlan) -> StoryPresentation:
        """Localize public titles when fiction writing begins."""
        return self.provider.generate_structured(
            system_instruction=(
                f"You are the Drafter. Writing now begins in {request.language}. Create one "
                "polished public story title and exactly one chapter title for every canonical "
                "chapter ID. Preserve the planned meaning, return no commentary, and use the "
                "requested fiction language for every title."
            ),
            prompt=(
                f"INTERNAL STORY SPECIFICATION:\n{json_text(request.agent_spec())}"
                f"\n\nENGLISH PLAN:\n{json_text(plan)}"
            ),
            schema=StoryPresentation,
            profile="planning",
        )

    def run(
        self,
        request: StoryRequest,
        world: WorldArtifact,
        characters: list[CharacterProfile],
        plan: StoryPlan,
        presentation: StoryPresentation,
        chapter: ChapterPlan,
        events: list[PlotEvent],
        relevant_history: list[PlotEvent],
        previous_chapter: str,
        promise_brief: str = "",
        *,
        style_examples: bool = False,
        scene_cards: list[SceneCard] | None = None,
        reader_context: dict | None = None,
    ) -> str:
        """Draft one fiction chapter from its validated event context.

        With scene cards (7.17) the chapter is written scene by scene from them, and the plan
        stops at this chapter: the ending and the chapters still to come told the Drafter how it
        all turns out, and the 7.10 drafts telegraphed it from the first page.
        """
        chapters = [item.model_dump(mode="json") for item in plan.chapters]
        plan_context = {
            "logline": plan.logline,
            "theme": plan.theme,
            "ending": plan.ending,
            "chapters": chapters,
        }
        if scene_cards:
            position = [item.id for item in plan.chapters].index(chapter.id)
            plan_context = {
                "logline": plan.logline,
                "theme": plan.theme,
                "chapters": chapters[: position + 1],
            }
        return self.provider.generate_text(
            system_instruction=(
                "You are the Drafter. Write only this first-draft fiction chapter body in "
                f"{request.language}, without a heading or process notes. Dramatize the supplied "
                "events in order, make causes and consequences visible, and render every supplied "
                "event as a distinct narrative development instead of compressing multiple events "
                "into summary. Play the decisive turns as scene instead of reporting them: let "
                "the characters speak in the voice recorded in their profile, and give spoken "
                "exchange its own paragraph under the dialogue-dash convention of the requested "
                "language rather than summarizing what was said. Break the paragraph at every "
                "new speaker or shift of attention instead of packing a whole sequence into one "
                "block. Hold this to the final chapter: a "
                "resolution is a scene, not an account of how matters ended. Expand Developed and "
                "Expansive stories through meaningful action, reaction, and consequence rather "
                "than repetition or decorative filler. Respect world rules, character intentions, "
                "continuity, and the qualitative narrative profile. When PROMISE OBLIGATIONS are "
                "supplied, deliver each one inside the event it names, through what happens and "
                "what is said, so the reader is left expecting, or satisfied, without ever being "
                "told so. Do not expose internal IDs or planning terminology."
                + (SCENE_CARD_CLAUSE if scene_cards else "")
                + f"{ORIENTATION_RULES}{style_clause(request, examples=style_examples)}"
            ),
            prompt=(
                f"{story_specification_header(request)}"
                f"\n\nWORLD:\n{json_text(world)}"
                f"\n\nREADER CONTEXT:\n{json_text(reader_context or {})}"
                f"\n\nRELEVANT CHARACTERS:\n{json_text(characters)}"
                f"\n\nGLOBAL PLAN:\n{json_text(plan_context)}"
                f"\n\nLOCALIZED PRESENTATION:\n{json_text(presentation)}"
                f"\n\nCURRENT CHAPTER:\n{json_text(chapter)}"
                f"\n\nORDERED EVENTS:\n{json_text(events)}"
                f"\n\nRELEVANT PRIOR EVENTS:\n{json_text(relevant_history)}"
                f"\n\nPREVIOUS CHAPTER:\n{previous_chapter or 'none'}"
                + (f"\n\nPROMISE OBLIGATIONS:\n{promise_brief}" if promise_brief else "")
                + (f"\n\nSCENE CARDS:\n{json_text(scene_cards)}" if scene_cards else "")
            ),
            profile="prose",
        )


class WriterAgent(Agent[ParagraphEdits]):
    """Apply the critic's coordinated notes to one chapter as paragraph edits (7.18)."""

    name = "writer"

    def run(
        self,
        request: StoryRequest,
        characters: list[CharacterProfile],
        plan: StoryPlan,
        presentation: StoryPresentation,
        chapter: ChapterPlan,
        events: list[PlotEvent],
        notes: list[RevisionNote],
        draft_body: str,
        previous_revised_chapter: str,
        retry_feedback: str = "",
        promise_brief: str = "",
        *,
        style_examples: bool = False,
    ) -> ParagraphEdits:
        """Return the edits that apply the notes to one chapter in the fiction language.

        Until 7.17 the Writer returned the whole chapter, and a light model mostly copied it
        back. writing/chapter_edits.py applies what comes back and keeps the rest as drafted.
        """
        return self.provider.generate_structured(
            system_instruction=(
                "You are the final Writer. The chapter below is split into numbered paragraphs. "
                "Apply the revision notes by editing those paragraphs, in "
                f"{request.language}, and return only your edits: 'replace' rewrites one "
                "paragraph, and 'insert_after' adds new paragraphs right after one, only to stage "
                "a beat a note asks for. Every critical or major note needs at least one visible "
                "edit that cites its id; a minor note may be left out. A paragraph you do not "
                "edit stays exactly as drafted, so returning no edit means the chapter is "
                "unchanged. Write the new text as finished prose, with no heading, commentary, "
                "note IDs or process language. Preserve correct material, planned causality, "
                "continuity and every distinct planned event, and honor the depth and pacing of "
                "the qualitative narrative profile. Keep every character speaking in the voice "
                "recorded in their profile, never turn a spoken exchange into reported summary, "
                "and keep a new paragraph for each new speaker or shift of attention. When "
                "PROMISE OBLIGATIONS are supplied, the edited chapter must still deliver every one "
                "of them inside the event it names: never drop an expectation the draft already "
                "planted."
                f"{ORIENTATION_RULES}{style_clause(request, examples=style_examples)}"
            ),
            prompt=(
                f"{story_specification_header(request)}"
                f"\n\nRELEVANT CHARACTERS:\n{json_text(characters)}"
                f"\n\nPLAN:\n{json_text(plan)}"
                f"\n\nLOCALIZED PRESENTATION:\n{json_text(presentation)}"
                f"\n\nCURRENT CHAPTER:\n{json_text(chapter)}"
                f"\n\nORDERED EVENTS:\n{json_text(events)}"
                f"\n\nREVISION NOTES:\n{json_text(notes)}"
                + (f"\n\nPROMISE OBLIGATIONS:\n{promise_brief}" if promise_brief else "")
                + f"\n\nPREVIOUS REVISED CHAPTER:\n{previous_revised_chapter or 'none'}"
                # The correction goes ahead of the paragraphs: in 7.17 it trailed the chapter
                # body, and the retry came back as the same copy of the draft.
                f"{retry_feedback}"
                f"\n\nCHAPTER PARAGRAPHS:\n{json_text(edit_request(draft_body))}"
            ),
            schema=ParagraphEdits,
            profile="rewrite",
        )
