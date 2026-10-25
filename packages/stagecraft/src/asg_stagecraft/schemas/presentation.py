"""The reader-facing shape of a story: its chapters, scene cards and body."""

from __future__ import annotations

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from ..planning.catalog_types import ModelId


class ChapterPresentation(BaseModel):
    """Localized public title for one internally planned chapter."""

    chapter_id: ModelId
    title: str = Field(min_length=1)


class SceneCard(BaseModel):
    """One scene the Drafter will write, drawn over the frozen plan before any prose (7.17)."""

    model_config = ConfigDict(extra="forbid")
    event_id: str = Field(description="The plan event this scene plays, exactly as given.")
    location_id: str = Field(
        default="", description="The id of the world location it happens in, or empty."
    )
    character_ids: list[str] = Field(
        min_length=1, description="Who is in the scene, by character id exactly as given."
    )
    wants: str = Field(
        min_length=1,
        description="In the fiction's language: what each character there wants right now.",
    )
    obstacle: str = Field(
        min_length=1,
        description="In the fiction's language: why the first attempt fails, what is in the way.",
    )
    turn: str = Field(
        min_length=1,
        description=(
            "In the fiction's language: what has changed by the end - a decision, a discovery "
            "or a reversal the reader sees happen."
        ),
    )
    detail: str = Field(
        min_length=1,
        description="In the fiction's language: one concrete sensory detail of the place.",
    )
    unsaid: str = Field(
        min_length=1,
        description=(
            "In the fiction's language: what the reader must understand without anyone saying it."
        ),
    )
    closing: str = Field(
        min_length=1,
        description="In the fiction's language: the image or the line the scene ends on.",
    )


class SceneCardsDraft(BaseModel):
    """The scene cards of a whole story, as scene_cards.json keeps them."""

    model_config = ConfigDict(extra="forbid")
    cards: list[SceneCard] = Field(min_length=1)


class StoryPresentation(BaseModel):
    """Localized titles created when the drafting phase begins."""

    title: str = Field(min_length=1)
    chapters: list[ChapterPresentation] = Field(min_length=1)

    @model_validator(mode="after")
    def chapter_ids_are_unique(self) -> StoryPresentation:
        """Require one unambiguous localized title per chapter."""
        identifiers = [item.chapter_id for item in self.chapters]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("presentation chapter ids must be unique")
        return self
