"""Read chapter orientation and propose bounded, source-grounded paragraph repairs."""

from pydantic import BaseModel, Field

from ..schemas import RevisionNote
from ..writing.chapter_edits import ParagraphEdits, edit_request
from ..writing.orientation import EVIDENCE_RULES, ORIENTATION_RULES, SPATIAL_RULES, ReaderSnapshot
from .base import Agent, json_text


class OrientationReview(ReaderSnapshot):
    """Reader evidence and chapter-local notes, anchored to the prose being assessed."""

    notes: list[RevisionNote] = Field(default_factory=list)
    faithful: bool = True


class SpatialReview(BaseModel):
    """An incompatible action and the exact setting evidence that makes it impossible."""

    action_quote: str = ""
    context_quote: str = ""
    correction: str = ""


class OrientationAgent(Agent[OrientationReview]):
    """Check what the reader actually learned, then repair only evidenced omissions."""

    name = "reader_orientation"

    def run(self, request, body: str, context: dict) -> OrientationReview:
        """Read one chapter through the standard agent interface."""
        return self.review(request, body, context)

    def review(self, request, body: str, context: dict, original: str = "") -> OrientationReview:
        """Audit context and verify a repair against both source and original chapter."""
        return self.provider.generate_structured(
            system_instruction=(
                "Review reader orientation in this chapter. Return notes only for confusing "
                "character introductions, place descriptions or missing transitions. Use "
                "category world_continuity, unique lowercase ids, major priority, "
                "empty chapter_ids "
                "and event_ids; evidence must quote at least four words from the affected "
                "prose. Instructions name the supplied public information that can fix it. "
                "Do not invent missing source facts. Set faithful=false if a repaired chapter "
                "changes an event, voice, secret or established fact of ORIGINAL, or invents "
                "a journey unsupported by source_events. Without ORIGINAL assess orientation "
                "only. No note is needed for an obvious transfer or a mere offstage mention."
                + ORIENTATION_RULES
                + EVIDENCE_RULES
            ),
            prompt=json_text(
                {
                    "language": request.language,
                    "READER CONTEXT": context,
                    "chapter": body,
                    "ORIGINAL": original,
                }
            ),
            schema=OrientationReview,
            profile="review",
        )

    def repair(self, request, body: str, context: dict, notes) -> ParagraphEdits:
        """Add minimal context without rewriting unrelated paragraphs or inventing events."""
        return self.provider.generate_structured(
            system_instruction=(
                f"Repair only the supplied orientation notes, in {request.language}. Return "
                "paragraph edits, with note_ids citing the notes each change answers. Keep "
                "all events, dialogue meanings, secrets, tense and perspective. Use only "
                "source-supported public context. Never add travel to explain a source "
                "contradiction. Prefer a short phrase within the affected paragraph."
                + ORIENTATION_RULES
            ),
            prompt=json_text(
                {"READER CONTEXT": context, "notes": notes, "paragraphs": edit_request(body)}
            ),
            schema=ParagraphEdits,
            profile="rewrite",
        )

    def review_space(self, context: str, action: str) -> SpatialReview:
        """Check a proposed literal action against the actor's current visible setting."""
        return self.provider.generate_structured(
            system_instruction=(
                "Check only physical spatial contradictions in ACTION against CURRENT CONTEXT. "
                "Return empty fields if compatible or uncertain. To reject, copy exact nonempty "
                "action_quote and context_quote from the respective inputs and give a short "
                "correction that stays in this setting. Do not judge acting quality or demand "
                "that every ordinary object be inventoried. Do not introduce future events."
                + SPATIAL_RULES
            ),
            prompt=json_text({"CURRENT CONTEXT": context, "ACTION": action}),
            schema=SpatialReview,
            profile="review",
        )
