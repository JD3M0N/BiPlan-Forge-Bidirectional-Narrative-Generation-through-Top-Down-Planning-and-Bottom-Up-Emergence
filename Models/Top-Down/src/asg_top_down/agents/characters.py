from .base import Agent, json_text
from ..narrative_db import NarrativeBlueprint
from ..schemas import (
    CharactersArtifact, StoryPlanArtifact, StoryRequest, TaxonomyBrief, WorldArtifact,
)


class CharacterDesignerAgent(Agent[CharactersArtifact]):
    name = "characters"

    def run(
        self, request: StoryRequest, plan: StoryPlanArtifact, world: WorldArtifact,
        blueprint: NarrativeBlueprint, repair_feedback: str = "",
        taxonomy_brief: TaxonomyBrief | None = None,
    ) -> CharactersArtifact:
        return self.provider.generate_structured(
            system_instruction=(
                "Create a compact cast with distinct goals. Every important action must follow a "
                "character intention, and opposition must pursue an active incompatible goal. Use "
                "retrieved role IDs for jungian_archetype and mark at least one character as main. "
                "Every main character starts with exactly two high sliders (7-10) and one low slider "
                "(1-4) among sympathy, competence, and proactivity. The low slider must be the focus, "
                "must ascend to 7-10, and the other two must remain high. Give concrete rationales. "
                "Supporting characters may omit slider arcs. Return all artifact text in English "
                "regardless of the requested fiction language."
            ),
            prompt=(f"REQUEST:\n{json_text(request)}\n\nPLAN:\n{json_text(plan)}"
                    f"\n\nWORLD:\n{json_text(world)}\n\nTAXONOMY ROLE PALETTE:\n"
                    f"{json_text(taxonomy_brief.roles) if taxonomy_brief else json_text(blueprint.roles)}"
                    f"\n\nTAXONOMY USAGE RULE:\n"
                    f"{taxonomy_brief.usage_rule if taxonomy_brief else 'Use roles flexibly.'}"
                    f"{repair_feedback}"),
            schema=CharactersArtifact,
        )
