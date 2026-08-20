from .base import Agent, json_text
from ..schemas import (
    CharactersArtifact, StoryPlanArtifact, StoryRequest, TaxonomyBrief, WorldArtifact,
)


class CharacterDesignerAgent(Agent[CharactersArtifact]):
    name = "characters"

    def run(
        self, request: StoryRequest, plan: StoryPlanArtifact, world: WorldArtifact,
        repair_feedback: str = "",
        taxonomy_brief: TaxonomyBrief | None = None,
    ) -> CharactersArtifact:
        return self.provider.generate_structured(
            system_instruction=(
                "Create a compact cast with distinct goals. Every important action must follow a "
                "character intention, and opposition must pursue an active incompatible goal. Use "
                "retrieved roles as flexible archetype inspiration and mark at least one character as main. "
                "Give stable lowercase IDs and valid initial world locations. Complete role, ensemble seat, "
                "competence domain, want, need, misbelief, wound, related strength/flaw and its concrete cost, "
                "personal rule, voice, and noticed details. Main characters may have positive, negative, or "
                "flat Sanderson slider arcs. Obey the schema invariants instead of forcing one universal shape. "
                "Represent every relationship with canonical source/target character IDs, kind, and current state. "
                "Supporting characters may omit slider arcs. Return all artifact text in English "
                "regardless of the requested fiction language."
            ),
            prompt=(f"NORMALIZED SPECIFICATION:\n{json_text(request.agent_spec())}\n\nPLAN:\n{json_text(plan)}"
                    f"\n\nWORLD:\n{json_text(world)}\n\nTAXONOMY ROLE PALETTE:\n"
                    f"{json_text(taxonomy_brief.roles) if taxonomy_brief else 'none'}"
                    f"\n\nTAXONOMY USAGE RULE:\n"
                    f"{taxonomy_brief.usage_rule if taxonomy_brief else 'Use roles flexibly.'}"
                    f"{repair_feedback}"),
            schema=CharactersArtifact,
        )
