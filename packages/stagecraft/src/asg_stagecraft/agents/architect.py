"""Structural reading of a premise offered to later stages as optional inspiration."""

from ..planning.skeleton_match import rank_skeletons, skeleton_query
from ..planning.skeletons import PERSONA_SUGGESTIONS, find_skeleton, functional_role_vocabulary
from ..schemas import NarrativeBlueprint, NarrativeBlueprintDraft, StoryRequest
from .base import Agent, json_text, story_specification_header

_SHORTLIST_LIMIT = 10


class StoryArchitectAgent(Agent[NarrativeBlueprint]):
    """Read a request against the skeleton catalog without constraining later stages."""

    name = "architect"

    def run(self, request: StoryRequest) -> NarrativeBlueprint:
        """Return one blueprint plus the ranking evidence behind it."""
        query = skeleton_query(request)
        considered = rank_skeletons(query, provider=self.provider, limit=_SHORTLIST_LIMIT)
        shortlist = [
            found.catalog_entry()
            for found in (find_skeleton(match.skeleton_id) for match in considered)
            if found
        ]
        draft = self.provider.generate_structured(
            system_instruction=(
                "Read the premise against a shortlist of plot skeletons and report how it already "
                "behaves, rather than assigning it a category. Choose the macroplot whose dramatic "
                "shape the premise most nearly inhabits. Then name the subplot skeletons "
                "that could plausibly run underneath it, because real stories usually "
                "layer several shapes at once. Let the NARRATIVE PROFILE CONTRACT decide "
                "how many: return an empty list when the profile asks for a single "
                "focused line, and one to three otherwise. Use only ids from the "
                "shortlist. "
                "Explain the reading in terms of what this specific premise wants, not in "
                "terms of the label. "
                "Propose role suggestions only for functions the premise clearly implies, pairing "
                "a functional role with an optional surface persona. Always propose one "
                "unexpected_angle: a concrete way this story should deliberately depart from the "
                "usual shape of the chosen macroplot, so the result is not a template. Return "
                "every field in English."
            ),
            prompt=(
                f"{story_specification_header(request)}"
                f"\n\nSKELETON SHORTLIST:\n{json_text(shortlist)}"
                f"\n\nFUNCTIONAL ROLE VOCABULARY:\n{json_text(functional_role_vocabulary())}"
                f"\n\nPERSONA SUGGESTIONS:\n{json_text(list(PERSONA_SUGGESTIONS))}"
            ),
            schema=NarrativeBlueprintDraft,
            profile="planning",
        )
        return NarrativeBlueprint(
            **draft.model_dump(),
            considered=considered,
            semantic_used=any(match.semantic_score is not None for match in considered),
        )
