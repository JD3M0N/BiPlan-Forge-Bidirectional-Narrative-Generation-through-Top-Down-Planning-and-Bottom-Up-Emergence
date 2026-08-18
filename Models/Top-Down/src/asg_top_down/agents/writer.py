from .base import Agent, json_text
from ..schemas import (
    ChapterPlan, CharactersArtifact, CraftVariant, IncrementalStorylineArtifact,
    NarrativeEntityGraphArtifact, StoryPlanArtifact, StoryRequest, WorldArtifact,
    TaxonomyBrief,
)


class ChapterWriterAgent(Agent[str]):
    name = "chapter_writer"

    def run(
        self,
        request: StoryRequest,
        plan: StoryPlanArtifact,
        world: WorldArtifact,
        characters: CharactersArtifact,
        variant: CraftVariant,
        storyline: IncrementalStorylineArtifact,
        nekg: NarrativeEntityGraphArtifact,
        chapter: ChapterPlan,
        previous_chapter: str,
        taxonomy_brief: TaxonomyBrief | None = None,
    ) -> str:
        nodes = [node for node in storyline.nodes if node.chapter_id == chapter.id]
        node_ids = {node.id for node in nodes}
        edges = [edge for edge in storyline.accepted_edges
                 if edge.source in node_ids or edge.target in node_ids]
        local_craft = next(item for item in variant.chapters if item.chapter_id == chapter.id)
        milestones = [item for item in variant.character_milestones if item.chapter_id == chapter.id]
        cycles = [item for item in variant.try_fail_cycles if item.chapter_id == chapter.id]
        story_plan_context = plan.model_dump(
            mode="json", exclude={"taxonomy_application", "archetypes"},
        )
        return self.provider.generate_text(
            system_instruction=(
                f"Write only the requested fiction chapter body in Markdown and in {request.language}. "
                "Every reader-visible word must use that output language, except proper nouns that must "
                "remain unchanged. Do not add a title or heading. Dramatize every accepted event in order "
                "while preserving intentions, causal effects, entity states, and the chapter ending. "
                "Realize the supplied global and local promise-progress-payoff guidance, character "
                "growth, and try-fail consequences through observable action and choice. Never expose "
                "planning terms, taxonomy names, IDs, slider names, or numeric values. Treat taxonomy "
                "movements and roles as flexible inspiration, never as a checklist or fixed sequence. "
                "Maintain style continuity with "
                "the complete previous chapter and respect the approximate chapter word budget."
            ),
            prompt=(
                f"REQUEST:\n{json_text(request)}\n\nPLAN:\n{json_text(story_plan_context)}"
                f"\n\nWORLD:\n{json_text(world)}\n\nCHARACTERS:\n{json_text(characters)}"
                f"\n\nGLOBAL CRAFT:\n{json_text({'master': variant.master_line, 'subplots': variant.subplots})}"
                f"\n\nCHAPTER CRAFT:\n{json_text(local_craft)}"
                f"\n\nCHARACTER MILESTONES:\n{json_text(milestones)}"
                f"\n\nTRY-FAIL CYCLES:\n{json_text(cycles)}"
                f"\n\nTAXONOMY BRIEF:\n{json_text(taxonomy_brief) if taxonomy_brief else 'none'}"
                f"\n\nCHAPTER:\n{json_text(chapter)}\n\nNODES:\n{json_text(nodes)}"
                f"\n\nCAUSAL LINKS:\n{json_text(edges)}\n\nCURRENT NEKG:\n{json_text(nekg)}"
                f"\n\nPREVIOUS CHAPTER:\n{previous_chapter or 'none'}"
            ),
        )
