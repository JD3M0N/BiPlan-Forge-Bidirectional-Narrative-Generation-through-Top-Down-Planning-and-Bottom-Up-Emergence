"""LLM dramatic review isolated from deterministic dependency validation."""

from __future__ import annotations

import json
from pydantic import BaseModel

from ..domain import ChapterPlan, StorylineCast, WorldArtifact
from .dependency import DependencyReport
from .graph import NarrativeGraphBackend
from .models import PlotNode, PlotNodeProposal, PlotNodeReview


def _json(value) -> str:
    def convert(item):
        if isinstance(item, BaseModel):
            return item.model_dump(mode="json")
        if isinstance(item, dict):
            return {key: convert(child) for key, child in item.items()}
        if isinstance(item, (list, tuple)):
            return [convert(child) for child in item]
        return item
    return json.dumps(convert(value), ensure_ascii=False, indent=2)


class DramaticReviewer:
    """Judge intention and dramatic movement with the same factual context."""

    def __init__(self, provider) -> None:
        self.provider = provider

    def review(self, proposal: PlotNodeProposal, chapter: ChapterPlan, anchor,
               world: WorldArtifact, characters: StorylineCast,
               dependency_report: DependencyReport, recent: list[PlotNode],
               graph: NarrativeGraphBackend, *, alignment_allowed: bool = True) -> PlotNodeReview:
        related = graph.related(proposal.subject.id, proposal.object.id, limit=10)
        alignment_rule = (
            "Alignment is allowed only if the supplied ending can occur immediately next."
            if alignment_allowed else
            "The minimum chapter development is not complete: set aligns_with_cen to false."
        )
        return self.provider.generate_structured(
            system_instruction=(
                "Review one internal plot event. Accept only if it has causal support, a character "
                "intention, active conflict, continuity, novelty, movement toward the chapter ending, "
                "world consistency, and an emotionally effective change. A replacement must be a "
                "complete candidate using canonical IDs and will be independently revalidated. The "
                "accepted flag describes the final candidate: set it true when either the original "
                "passes or the supplied revised candidate resolves every review issue. Set "
                "aligns_with_cen only when the candidate makes the supplied ending an immediate next "
                "event. The candidate is an internal event: never require it to match the ending's "
                "verb or object, and never copy either the begin-anchor SVO or end-anchor SVO into a "
                "replacement. Advancing toward the ending means establishing its prerequisites, not "
                "performing the ending early. Never apply an end anchor effect early or contradict an "
                "end anchor precondition. Return internal analysis in English."
                f" {alignment_rule} For any movement replacement, location_id is the actor's current source location "
                "and the adjacent destination belongs only in a typed location effect."
            ),
            prompt=(f"CANDIDATE:\n{_json(proposal)}\n\nCHAPTER:\n{_json(chapter)}"
                    f"\n\nEND TARGET:\n{_json({'subject': anchor.end_subject, 'verb': anchor.end_verb, 'object': anchor.end_object, 'location_id': anchor.end_location_id})}"
                    f"\n\nWORLD:\n{_json(world)}\n\nCHARACTERS:\n{_json(characters)}"
                    f"\n\nDETERMINISTIC DEPENDENCY REPORT:\n{_json(dependency_report)}"
                    f"\n\nRECENT STORYLINE:\n{_json(recent)}"
                    f"\n\nRELEVANT ENTITY STATE AND RELATIONS:\n{_json(related)}"),
            schema=PlotNodeReview,
        )
