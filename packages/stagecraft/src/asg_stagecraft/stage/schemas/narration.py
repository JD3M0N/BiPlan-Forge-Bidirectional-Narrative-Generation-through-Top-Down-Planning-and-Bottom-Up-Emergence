"""What the narrator reads and writes: chapters, reviews, retellings and selections."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ...formats import NarrativeVoice
from ...schemas import ModelId
from ...writing.orientation import ReaderSnapshot

# --------------------------------------------------------------------------------------
# Narration
# --------------------------------------------------------------------------------------


class ChapterNarration(BaseModel):
    """One narrated chapter and the performed material it was written from."""

    chapter_id: ModelId
    chapter_index: int = Field(ge=1)
    scene_ids: list[str] = Field(default_factory=list)
    turns_available: int = Field(ge=0)
    turns_visible: int = Field(ge=0)
    words: int = Field(ge=0)
    # Zero for a chapter left out: "absent" means this point of view saw nothing to narrate
    # there, so no call was made and the chapter is not in story.md (7.3).
    attempts: int = Field(ge=0)
    source: Literal["narrator", "fallback", "absent"]


class NarrationArtifact(BaseModel):
    """How the prose was narrated from the log: the voice, the narrator, and every chapter.

    Contract 2 (7.3) adds who was asked to narrate, how the narrator was finally chosen, the
    tone the author asked for, and chapters recorded as absent. A contract 1 file still loads.
    Contract 4 (7.12): a chapter the review disputes ships as its best narrated attempt, never
    as the fallback, and each review file records blocking, advisory and discarded findings.
    """

    contract_version: str = "4"
    narrative_voice: NarrativeVoice
    narrator_character_id: str = ""
    # The name as the person typed it, before it was resolved against the cast.
    requested_narrator: str = ""
    narrator_source: Literal["", "none", "requested", "protagonist", "most_turns"] = ""
    narration_tone: str = ""
    chapters: list[ChapterNarration] = Field(default_factory=list)


class NarrationFinding(BaseModel):
    """One editorial issue, anchored to prose or a visible source turn."""

    model_config = ConfigDict(extra="forbid")
    code: Literal[
        "INVENTED_EVENT",
        "OMITTED_CONSEQUENCE",
        "CONTRADICTION",
        "VOICE",
        "INTERNAL_MARKER",
        "REPETITION",
        "CHARACTER_CONTEXT",
        "PLACE_CONTEXT",
        "MISSING_TRANSITION",
    ]
    quote: str = ""
    turn_ids: list[str] = Field(default_factory=list)
    correction: str = Field(min_length=1)


class NarrationReview(ReaderSnapshot):
    """A bounded editorial review; it never writes new story events."""

    model_config = ConfigDict(extra="forbid")
    findings: list[NarrationFinding] = Field(default_factory=list)


class ReportedLine(BaseModel):
    """One item of the log retold as past-tense narration, so the narrator has nothing to copy."""

    model_config = ConfigDict(extra="forbid")
    id: str = Field(
        description="The id of the item this retells, exactly as given (L1, G1, T1, E1...)."
    )
    report: str = Field(
        min_length=1,
        description=(
            "One short sentence in the past tense, the third person and the fiction's language, "
            "with its accents, in your own words: what was said in indirect style ('Gaspar "
            "insistió en soltar el lastre'), done ('Ilse golpeó la borda'), felt ('Aleth temía "
            "al Consejo') or what happened. Never quote the item."
        ),
    )


class ReportedLines(BaseModel):
    """Indirect-style retellings of the lines a chapter does not turn on (7.16)."""

    model_config = ConfigDict(extra="forbid")
    lines: list[ReportedLine] = Field(default_factory=list)
    memorable: list[str] = Field(
        default_factory=list,
        description=(
            "Ids of the lines worth hearing in the speaker's own words - a decision, a refusal, "
            "a confession, a reveal, a line that turns the scene - the most memorable first. "
            "Rank several of them."
        ),
    )


class SelectedMoment(BaseModel):
    """A run of consecutive lines a chapter tells one way (7.17, narration_method=selected)."""

    model_config = ConfigDict(extra="forbid")
    lines: list[str] = Field(
        min_length=1,
        description="Ids of the consecutive lines of this moment, exactly as given (L1, L2...).",
    )
    treatment: Literal["scene", "summary"] = Field(
        description=(
            "scene: played out in full, its lines as dialogue - only for what the chapter turns "
            "on. summary: passes in one sentence of narration."
        )
    )
    gist: str = Field(
        min_length=1,
        description=(
            "One sentence in the fiction's language, in the past tense and with its accents: "
            "what happens or changes in this moment, in your own words. Never quote a line."
        ),
    )
    bridge: str = Field(
        default="",
        description=(
            "Only when this moment opens a new scene: one sentence in the fiction's language "
            "that carries the reader there - where, when, who is there - from the scene's setting."
        ),
    )


class ChapterSelection(BaseModel):
    """The moments one chapter is told through, chosen from its log before any prose."""

    model_config = ConfigDict(extra="forbid")
    moments: list[SelectedMoment] = Field(default_factory=list)


class WorldEventAssessment(BaseModel):
    """Semantic review of a proposed intervention against established circumstances."""

    model_config = ConfigDict(extra="forbid")
    compatible: bool
    introduces_solution: bool
    reveals_future_gate: bool
    reason: str
