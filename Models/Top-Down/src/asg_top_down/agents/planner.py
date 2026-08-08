from .base import Agent, json_text
from ..schemas import StoryPlanArtifact, StoryRequest
from ..taxonomies import TaxonomyRepository


def taxonomy_query(request: StoryRequest) -> str:
    """Build the exact text scored by the taxonomy repository."""
    return f"{request.original_prompt} {request.premise} {request.genre} {request.tone}"


class PlannerAgent(Agent[StoryPlanArtifact]):
    name = "planner"

    def __init__(self, provider, taxonomies: TaxonomyRepository) -> None:
        super().__init__(provider)
        self.taxonomies = taxonomies

    def run(self, request: StoryRequest) -> StoryPlanArtifact:
        catalog = self.taxonomies.recommend_archetypes(taxonomy_query(request))
        plan = self.provider.generate_structured(
            system_instruction=(
                "Eres planificador narrativo. Selecciona exactamente un arquetipo principal "
                "del catálogo y como máximo dos secundarios distintos. Fundamenta la elección "
                "en el prompt y crea una progresión causal de al menos tres fases. Usa los IDs "
                "canónicos sin inventar arquetipos."
            ),
            prompt=f"REQUISITOS:\n{json_text(request)}\n\nCATÁLOGO:\n{json_text(catalog)}",
            schema=StoryPlanArtifact,
        )
        ids = [plan.archetypes.primary, *plan.archetypes.secondary]
        known_candidates = {item.id for item in catalog}
        if not set(ids) <= known_candidates:
            raise ValueError("Planner selected an archetype outside the supplied shortlist")
        return plan
