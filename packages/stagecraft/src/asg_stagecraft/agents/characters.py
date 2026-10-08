"""Compact cast construction."""

from ..planning.guidance_models import CompositionArtifact
from ..planning.skeletons import functional_role_vocabulary
from ..schemas import CharactersArtifact, NarrativeBlueprint, StoryRequest, WorldArtifact
from .base import Agent, json_text, story_specification_header


class CharacterDesignerAgent(Agent[CharactersArtifact]):
    """Represent CharacterDesignerAgent data and behavior."""

    name = "characters"

    def run(
        self,
        request: StoryRequest,
        world: WorldArtifact,
        blueprint: NarrativeBlueprint | CompositionArtifact | None = None,
        feedback: str = "",
    ) -> CharactersArtifact:
        """Design the cast; feedback, only on a repair, names what the last cast left out."""
        role_labels = ""
        if blueprint is not None:
            vocabulary = ", ".join(functional_role_vocabulary())
            role_labels = (
                "Set functional_role, when it is obvious, to one of: "
                f"{vocabulary}. Set persona to a short everyday word for the kind of character "
                "they are in the fiction. Leave either field empty when nothing fits; never "
                "force a label. "
            )
        return self.provider.generate_structured(
            system_instruction=(
                "Create a purposeful cast scaled to the qualitative narrative profile, with stable "
                "lowercase IDs, distinct goals, credible motivations, active conflicts, concise "
                "arcs, and recognizable voices. Keep Essential casts lean. Give Developed stories "
                "supporting characters capable of sustaining a functional secondary arc. Give "
                "Expansive stories multiple interacting arcs capable of sustaining meaningful "
                "subplots. Opposition must pursue a goal incompatible with the protagonist's goal. "
                f"Relationships must use canonical character IDs. {role_labels}"
                "Do not use scores, sliders, or hidden planning labels. "
                "Return artifact content in English."
            ),
            prompt=(
                f"{story_specification_header(request, blueprint, audience='characters')}"
                f"\n\nWORLD:\n{json_text(world)}"
                f"{feedback}"
            ),
            schema=CharactersArtifact,
            profile="planning",
        )
