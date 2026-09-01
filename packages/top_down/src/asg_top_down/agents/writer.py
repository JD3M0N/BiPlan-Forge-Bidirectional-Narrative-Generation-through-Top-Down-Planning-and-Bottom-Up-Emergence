"""First-draft generation and note-driven chapter rewriting."""

from ..profiles import profile_guidance
from ..schemas import (
    ChapterPlan,
    CharacterProfile,
    PlotEvent,
    RevisionNote,
    StoryPlan,
    StoryPresentation,
    StoryRequest,
    WorldArtifact,
)
from .base import Agent, json_text


class DrafterAgent(Agent[str]):
    """Create localized titles and the first prose draft."""

    name = "drafter"

    def presentation(self, request: StoryRequest, plan: StoryPlan) -> StoryPresentation:
        """Localize public titles when fiction writing begins."""
        return self.provider.generate_structured(
            system_instruction=(
                f"You are the Drafter. Writing now begins in {request.language}. Create one polished public "
                "story title and exactly one chapter title for every canonical chapter ID. Preserve the "
                "planned meaning, return no commentary, and use the requested fiction language for every "
                "title."
            ),
            prompt=(
                f"INTERNAL STORY SPECIFICATION:\n{json_text(request.agent_spec())}"
                f"\n\nENGLISH PLAN:\n{json_text(plan)}"
            ),
            schema=StoryPresentation,
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
    ) -> str:
        """Draft one fiction chapter from its validated event context."""
        plan_context = {
            "logline": plan.logline,
            "theme": plan.theme,
            "ending": plan.ending,
            "chapters": [item.model_dump(mode="json") for item in plan.chapters],
        }
        return self.provider.generate_text(
            system_instruction=(
                f"You are the Drafter. Write only this first-draft fiction chapter body in "
                f"{request.language}, without a heading or process "
                "notes. Dramatize the supplied events in order, make causes and consequences visible, and "
                "respect world rules, character intentions, continuity, and the qualitative narrative profile. "
                "Do not expose internal IDs or planning terminology."
            ),
            prompt=(
                f"STORY SPECIFICATION:\n{json_text(request.agent_spec())}"
                f"\n\nNARRATIVE PROFILE CONTRACT:\n{profile_guidance(request.narrative_profile)}"
                f"\n\nWORLD:\n{json_text(world)}"
                f"\n\nRELEVANT CHARACTERS:\n{json_text(characters)}"
                f"\n\nGLOBAL PLAN:\n{json_text(plan_context)}"
                f"\n\nLOCALIZED PRESENTATION:\n{json_text(presentation)}"
                f"\n\nCURRENT CHAPTER:\n{json_text(chapter)}"
                f"\n\nORDERED EVENTS:\n{json_text(events)}"
                f"\n\nRELEVANT PRIOR EVENTS:\n{json_text(relevant_history)}"
                f"\n\nPREVIOUS CHAPTER:\n{previous_chapter or 'none'}"
            ),
        )


class WriterAgent(Agent[str]):
    """Apply the critic's coordinated notes to one chapter."""

    name = "writer"

    def run(
        self,
        request: StoryRequest,
        plan: StoryPlan,
        presentation: StoryPresentation,
        chapter: ChapterPlan,
        events: list[PlotEvent],
        notes: list[RevisionNote],
        draft_body: str,
        previous_revised_chapter: str,
        retry_feedback: str = "",
    ) -> str:
        """Rewrite one chapter body in the requested fiction language."""
        return self.provider.generate_text(
            system_instruction=(
                f"You are the final Writer. Rewrite only this chapter body in {request.language}; return no "
                "heading, commentary, note IDs, or process language. Apply every supplied global and local "
                "revision note, preserve correct material, planned causality, and continuity, and honor the "
                "depth and pacing of the qualitative narrative profile. Coordinate the opening with the "
                "previously revised chapter."
            ),
            prompt=(
                f"STORY SPECIFICATION:\n{json_text(request.agent_spec())}"
                f"\n\nNARRATIVE PROFILE CONTRACT:\n{profile_guidance(request.narrative_profile)}"
                f"\n\nPLAN:\n{json_text(plan)}"
                f"\n\nLOCALIZED PRESENTATION:\n{json_text(presentation)}"
                f"\n\nCURRENT CHAPTER:\n{json_text(chapter)}"
                f"\n\nORDERED EVENTS:\n{json_text(events)}"
                f"\n\nREVISION NOTES:\n{json_text(notes)}"
                f"\n\nPREVIOUS REVISED CHAPTER:\n{previous_revised_chapter or 'none'}"
                f"\n\nORIGINAL CHAPTER BODY:\n{draft_body}"
                f"{retry_feedback}"
            ),
        )
