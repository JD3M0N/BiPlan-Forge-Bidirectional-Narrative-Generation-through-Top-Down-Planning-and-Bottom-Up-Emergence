from .base import Agent, json_text
from ..schemas import (
    ChapterPlan, ChapterWritingBrief, CharactersArtifact, IncrementalStorylineArtifact,
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
        writing_brief: ChapterWritingBrief,
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
        narrative_events = [node.model_dump(
            mode="json",
            exclude={"id", "chapter_id", "node_type", "timestamp", "global_order", "local_order"},
        ) for node in nodes]
        causal_guidance = [
            f"A prior accepted event {edge.relation} the current chapter event."
            for edge in edges
        ]
        entity_context = {
            "entities": [entity.model_dump(mode="json", exclude={"id", "last_event_id"})
                         for entity in nekg.entities],
            "relations": [relation.model_dump(
                mode="json", exclude={"plot_node_id", "timestamp"},
            ) for relation in nekg.relations],
        }
        story_plan_context = plan.model_dump(
            mode="json", exclude={"taxonomy_application", "archetypes"},
        )
        chapter_context = chapter.model_dump(mode="json", exclude={"id", "order"})
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
                f"\n\nCHAPTER WRITING BRIEF:\n{json_text(writing_brief)}"
                f"\n\nTAXONOMY BRIEF:\n{json_text(taxonomy_brief) if taxonomy_brief else 'none'}"
                f"\n\nCHAPTER:\n{json_text(chapter_context)}"
                f"\n\nNARRATIVE EVENTS:\n{json_text(narrative_events)}"
                f"\n\nCAUSAL GUIDANCE:\n{json_text(causal_guidance)}"
                f"\n\nCURRENT ENTITY CONTEXT:\n{json_text(entity_context)}"
                f"\n\nPREVIOUS CHAPTER:\n{previous_chapter or 'none'}"
            ),
        )
