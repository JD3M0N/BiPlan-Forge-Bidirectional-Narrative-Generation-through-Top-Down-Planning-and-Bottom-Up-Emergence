"""Theater-script generation: native drafting, adaptation from prose, and note-driven revision."""

from ..schemas import (
    ActScriptDraft,
    ChapterPlan,
    CharacterProfile,
    PlotEvent,
    RevisionNote,
    ScriptFrame,
    ScriptPresentation,
    StoryPlan,
    StoryPresentation,
    StoryRequest,
    WorldArtifact,
)
from .base import Agent, json_text, story_specification_header

STAGING_RULES = (
    "Cite every event by its ID from the ACT ANCHOR INDEX, in plan order; start a new scene "
    "whenever the place or the continuous time changes. Use only the locations and characters "
    "listed in the ACT ANCHOR INDEX. Write every scene objective in English, as a concrete, "
    "playable want. Only a character in a scene's cast may speak or act there; a minor figure "
    "may appear only inside a stage direction, never in the cast. A stage direction shows only "
    "what an audience can see or hear on stage: no thoughts, no backstory, no narrator's "
    "commentary. Never expose internal IDs or planning terminology in any text a reader would "
    "see."
)


class PlaywrightAgent(Agent[ActScriptDraft]):
    """Create localized script titles and the first act of scenes for a chapter."""

    name = "playwright"

    def presentation(
        self,
        request: StoryRequest,
        plan: StoryPlan,
        characters,
    ) -> ScriptPresentation:
        """Localize the script's title, act titles, and printed-script frame."""
        character_index = [
            {"id": item.id, "name": item.name, "role": item.role} for item in characters.characters
        ]
        return self.provider.generate_structured(
            system_instruction=(
                f"You are the Playwright. Writing now begins in {request.language}. Create one "
                "polished public script title and exactly one act title for every canonical "
                "chapter ID. Also create the printed-script frame: localized words for the cast "
                "heading, the act word, and the scene word, plus one short cast description per "
                "character worth naming for a reader of the printed script. Preserve the planned "
                "meaning, return no commentary, and use the requested fiction language for every "
                "title and label."
            ),
            prompt=(
                f"INTERNAL STORY SPECIFICATION:\n{json_text(request.agent_spec())}"
                f"\n\nENGLISH PLAN:\n{json_text(plan)}"
                f"\n\nCHARACTERS:\n{json_text(character_index)}"
            ),
            schema=ScriptPresentation,
            profile="planning",
        )

    def run(
        self,
        request: StoryRequest,
        world: WorldArtifact,
        characters: list[CharacterProfile],
        plan: StoryPlan,
        presentation: ScriptPresentation,
        chapter: ChapterPlan,
        events: list[PlotEvent],
        relevant_history: list[PlotEvent],
        previous_act: str,
        anchor_index: str,
        promise_brief: str = "",
        repair_feedback: str = "",
    ) -> ActScriptDraft:
        """Draft one chapter as a first act of scenes from its validated event context."""
        plan_context = {
            "logline": plan.logline,
            "theme": plan.theme,
            "ending": plan.ending,
            "chapters": [item.model_dump(mode="json") for item in plan.chapters],
        }
        return self.provider.generate_structured(
            system_instruction=(
                "You are the Playwright. Write only this first-draft act of scenes in "
                f"{request.language}. {STAGING_RULES} Dramatize the supplied events in order, "
                "make causes and consequences visible, and stage every supplied event as its "
                "own scene development instead of compressing multiple events into one "
                "exchange. Let the characters speak in the voice recorded in their profile. "
                "Expand Developed and Expansive stories through meaningful action, reaction, "
                "and consequence rather than repetition or decorative filler. Respect world "
                "rules, character intentions, continuity, and the qualitative narrative "
                "profile. When PROMISE OBLIGATIONS are supplied, deliver each one inside the "
                "event it names, through what happens and what is said."
            ),
            prompt=(
                f"{story_specification_header(request)}"
                f"\n\nWORLD:\n{json_text(world)}"
                f"\n\nRELEVANT CHARACTERS:\n{json_text(characters)}"
                f"\n\nGLOBAL PLAN:\n{json_text(plan_context)}"
                f"\n\nLOCALIZED PRESENTATION:\n{json_text(presentation)}"
                f"\n\nCURRENT CHAPTER:\n{json_text(chapter)}"
                f"\n\nORDERED EVENTS:\n{json_text(events)}"
                f"\n\nRELEVANT PRIOR EVENTS:\n{json_text(relevant_history)}"
                f"\n\nPREVIOUS ACT:\n{previous_act or 'none'}"
                + (f"\n\nPROMISE OBLIGATIONS:\n{promise_brief}" if promise_brief else "")
                + f"\n\n{anchor_index}"
                + repair_feedback
            ),
            schema=ActScriptDraft,
            profile="prose",
        )


class ScriptWriterAgent(Agent[ActScriptDraft]):
    """Apply the script critic's coordinated notes to one act."""

    name = "script_writer"

    def run(
        self,
        request: StoryRequest,
        characters: list[CharacterProfile],
        plan: StoryPlan,
        presentation: ScriptPresentation,
        chapter: ChapterPlan,
        events: list[PlotEvent],
        notes: list[RevisionNote],
        original_act: ActScriptDraft,
        previous_revised_act: str,
        anchor_index: str,
        retry_feedback: str = "",
        promise_brief: str = "",
    ) -> ActScriptDraft:
        """Rewrite one act in the requested fiction language, applying every supplied note."""
        return self.provider.generate_structured(
            system_instruction=(
                f"You are the Script Writer. Rewrite only this act in {request.language}; "
                f"return no commentary or process language. {STAGING_RULES} Apply every "
                "supplied global and local revision note, preserve correct material, planned "
                "causality, and continuity, and honor the depth and pacing of the qualitative "
                "narrative profile. Preserve every distinct planned event and expand through "
                "meaningful action, reaction, and consequence rather than summary, repetition, "
                "or decorative filler. Coordinate the opening with the previously revised act. "
                "When PROMISE OBLIGATIONS are supplied, the rewrite must still deliver every "
                "one of them inside the event it names."
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
                + f"\n\nPREVIOUS REVISED ACT:\n{previous_revised_act or 'none'}"
                f"\n\n{anchor_index}"
                f"\n\nORIGINAL ACT:\n{json_text(original_act)}"
                f"{retry_feedback}"
            ),
            schema=ActScriptDraft,
            profile="rewrite",
        )


class ScriptAdapterAgent(Agent[ActScriptDraft]):
    """Convert the final narrative prose into the same theater-script contract."""

    name = "script_adapter"

    def frame(
        self,
        request: StoryRequest,
        characters,
        presentation: StoryPresentation,
    ) -> ScriptFrame:
        """Create the printed-script frame for a story that was already drafted as prose."""
        character_index = [
            {"id": item.id, "name": item.name, "role": item.role} for item in characters.characters
        ]
        return self.provider.generate_structured(
            system_instruction=(
                f"You are the Script Adapter. Writing in {request.language}, create the "
                "printed-script frame for the story below: localized words for the cast "
                "heading, the act word, and the scene word, plus one short cast description "
                "per character worth naming for a reader of the printed script. Return no "
                "commentary."
            ),
            prompt=(
                f"STORY TITLE:\n{presentation.title}"
                f"\n\nCHAPTER TITLES:\n{json_text(presentation.chapters)}"
                f"\n\nCHARACTERS:\n{json_text(character_index)}"
            ),
            schema=ScriptFrame,
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
        prose_body: str,
        previous_act: str,
        anchor_index: str,
        repair_feedback: str = "",
    ) -> ActScriptDraft:
        """Adapt one final prose chapter into an act of scenes, faithful to its every beat."""
        return self.provider.generate_structured(
            system_instruction=(
                "You are the Script Adapter. Convert only this finished prose chapter into an "
                f"act of scenes in {request.language}. {STAGING_RULES} Be faithful to the "
                "prose: keep every beat, consequence, and line of dialogue in order, turn "
                "narration into performable stage directions, turn reported speech into "
                "spoken dialogue, and never invent an event the prose does not already "
                "contain. Coordinate the opening with the previously adapted act."
            ),
            prompt=(
                f"{story_specification_header(request)}"
                f"\n\nWORLD:\n{json_text(world)}"
                f"\n\nRELEVANT CHARACTERS:\n{json_text(characters)}"
                f"\n\nLOCALIZED PRESENTATION:\n{json_text(presentation)}"
                f"\n\nCURRENT CHAPTER:\n{json_text(chapter)}"
                f"\n\nORDERED EVENTS:\n{json_text(events)}"
                f"\n\nPREVIOUS ACT:\n{previous_act or 'none'}"
                f"\n\n{anchor_index}"
                f"\n\nFINAL PROSE CHAPTER:\n{prose_body}"
                f"{repair_feedback}"
            ),
            schema=ActScriptDraft,
            profile="rewrite",
        )
