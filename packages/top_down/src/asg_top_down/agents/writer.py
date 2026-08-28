"""Chapter prose generation."""

from ..schemas import (
    ChapterPlan,
    CharacterProfile,
    PlotEvent,
    StoryPlan,
    StoryRequest,
    WorldArtifact,
)
from .base import Agent, json_text


class ChapterWriterAgent(Agent[str]):
    """Represent ChapterWriterAgent data and behavior."""

    name = "chapter_writer"

    def run(
        self,
        request: StoryRequest,
        world: WorldArtifact,
        characters: list[CharacterProfile],
        plan: StoryPlan,
        chapter: ChapterPlan,
        events: list[PlotEvent],
        previous_chapter: str,
    ) -> str:
        """Run the ChapterWriterAgent workflow."""
        plan_context = {
            "logline": plan.logline,
            "theme": plan.theme,
            "ending": plan.ending,
            "chapters": [item.model_dump(mode="json") for item in plan.chapters],
        }
        return self.provider.generate_text(
            system_instruction=(
                f"Write only this fiction chapter body in {request.language}, without a heading or process "
                "notes. Dramatize the supplied events in order, make causes and consequences visible, and "
                "respect world rules, character intentions, continuity, and the approximate word budget. "
                "Do not expose internal IDs or planning terminology."
            ),
            prompt=(
                f"STORY SPECIFICATION:\n{json_text(request.agent_spec())}"
                f"\n\nWORLD:\n{json_text(world)}"
                f"\n\nRELEVANT CHARACTERS:\n{json_text(characters)}"
                f"\n\nGLOBAL PLAN:\n{json_text(plan_context)}"
                f"\n\nCURRENT CHAPTER:\n{json_text(chapter)}"
                f"\n\nORDERED EVENTS:\n{json_text(events)}"
                f"\n\nPREVIOUS CHAPTER:\n{previous_chapter or 'none'}"
            ),
        )
