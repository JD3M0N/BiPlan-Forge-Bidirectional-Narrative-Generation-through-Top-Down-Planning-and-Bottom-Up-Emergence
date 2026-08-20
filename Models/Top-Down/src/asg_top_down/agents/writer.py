from .base import Agent, json_text
from ..schemas import (
    ChapterPlan, ChapterWritingBrief, StoryPlanArtifact, StoryRequest, WorldArtifact,
)


class ChapterWriterAgent(Agent[str]):
    name = "chapter_writer"

    def run(
        self, request: StoryRequest, plan: StoryPlanArtifact, world: WorldArtifact,
        writing_brief: ChapterWritingBrief, chapter: ChapterPlan, previous_chapter: str,
    ) -> str:
        story_context = plan.model_dump(mode="json", exclude={"taxonomy_application"})
        chapter_context = chapter.model_dump(mode="json", exclude={"id", "order"})
        return self.provider.generate_text(
            system_instruction=(
                f"Write only this fiction chapter body in Markdown and in {request.language}. Do not "
                "add a title or heading. Dramatize every supplied event in order from the BEFORE-state; "
                "the planned changes must occur on page rather than already being true at the start. "
                "Use the behavioral cards and reader-experience guidance naturally. Never expose IDs, "
                "taxonomies, slider names or numbers, promise labels, or future payoffs. Maintain continuity "
                "with the previous chapter and respect the approximate word budget."
            ),
            prompt=(f"NORMALIZED SPECIFICATION:\n{json_text(request.agent_spec())}"
                    f"\n\nSTORY FRAME AND PLAN:\n{json_text(story_context)}"
                    f"\n\nWORLD RULES:\n{json_text(world)}"
                    f"\n\nSANITIZED CHAPTER BRIEF, FACTS, AND BEFORE-STATE:\n{json_text(writing_brief)}"
                    f"\n\nCHAPTER:\n{json_text(chapter_context)}"
                    f"\n\nPREVIOUS CHAPTER:\n{previous_chapter or 'none'}"),
        )
