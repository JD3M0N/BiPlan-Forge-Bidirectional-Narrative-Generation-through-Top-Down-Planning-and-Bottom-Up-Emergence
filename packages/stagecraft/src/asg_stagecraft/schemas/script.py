"""The theater script: lines, scenes, acts and the play they assemble into."""

from __future__ import annotations

from typing import Literal

from pydantic import (
    BaseModel,
    Field,
)

from ..formats import ScriptMethod
from ..planning.catalog_types import ModelId
from ..planning.profiles import NarrativeProfile
from .presentation import StoryPresentation


class ScriptLine(BaseModel):
    """One line of a scene: words a character speaks, or a stage direction the audience sees."""

    kind: Literal["dialogue", "direction"]
    speaker_id: str = Field(
        default="",
        description="Character ID of the speaker, for a dialogue line. Empty for a direction.",
    )
    parenthetical: str = Field(
        default="",
        description=(
            "Optional brief acting note for a dialogue line, without parentheses. "
            "Empty for a direction."
        ),
    )
    actor_ids: list[str] = Field(
        default_factory=list,
        description="Character IDs of everyone who acts in a stage direction. Empty for dialogue.",
    )
    text: str = Field(
        min_length=1,
        description=(
            "The spoken words for dialogue, or what the audience sees or hears, for a direction. "
            "In the fiction language."
        ),
    )


class SceneCastMember(BaseModel):
    """One character on stage in a scene, with the objective the actor plays there."""

    character_id: str = Field(description="Character ID from the ACT ANCHOR INDEX.")
    objective: str = Field(
        min_length=1,
        description=(
            "In English: what this character wants in this scene, as a concrete, playable want. "
            "Never printed in the rendered script."
        ),
    )


class ScriptSceneDraft(BaseModel):
    """One scene as the model proposed it, before script.py has judged it."""

    event_ids: list[str] = Field(
        min_length=1,
        description="Plan event IDs this scene stages, from the ACT ANCHOR INDEX, in plan order.",
    )
    location_id: str | None = Field(
        default=None,
        description=(
            "Location ID from the ACT ANCHOR INDEX. Null only when none of this scene's events "
            "declares a location."
        ),
    )
    setting: str = Field(
        min_length=1,
        description="Opening stage direction in the fiction language: place and moment, as seen.",
    )
    cast: list[SceneCastMember] = Field(
        min_length=1,
        description="Every character on stage in this scene.",
    )
    lines: list[ScriptLine] = Field(min_length=1)


class ActScriptDraft(BaseModel):
    """One chapter written as an act of scenes, before script.py has judged it."""

    scenes: list[ScriptSceneDraft] = Field(min_length=1)


class ScriptScene(ScriptSceneDraft):
    """One scene script.py already validated against the frozen plan.

    id and number are derived, never authored: the model proposes a ScriptSceneDraft and
    materialize_act mints the identity once the anchors and staging hold.
    """

    id: ModelId
    number: int = Field(ge=1)


class ActScript(BaseModel):
    """One act script.py already validated: a chapter staged as scenes."""

    chapter_id: ModelId
    number: int = Field(ge=1)
    title: str = Field(min_length=1)
    scenes: list[ScriptScene] = Field(min_length=1)
    observations: list[str] = Field(default_factory=list)

    def as_draft(self) -> ActScriptDraft:
        """Strip validated identity, returning the shape the Script Writer receives and returns."""
        return ActScriptDraft(
            scenes=[
                ScriptSceneDraft(**scene.model_dump(exclude={"id", "number"}))
                for scene in self.scenes
            ]
        )


class CastNote(BaseModel):
    """One optional description of a character for the printed cast list."""

    character_id: str = Field(description="Character ID from characters.json.")
    description: str = Field(min_length=1)


class ScriptFrame(BaseModel):
    """Labels and cast notes for the printed script, created once per run."""

    cast_heading: str = Field(min_length=1, description="Localized heading, e.g. 'Personajes'.")
    act_label: str = Field(min_length=1, description="Localized act word, e.g. 'Acto'.")
    scene_label: str = Field(min_length=1, description="Localized scene word, e.g. 'Escena'.")
    cast: list[CastNote] = Field(default_factory=list)


class ScriptPresentation(StoryPresentation):
    """Localized titles plus the printed-script frame, created when script writing begins."""

    frame: ScriptFrame


class PlayCastMember(BaseModel):
    """One member of the dramatis personae, as printed in script.json."""

    character_id: ModelId
    name: str = Field(min_length=1)
    description: str = ""


class PlayScript(BaseModel):
    """The complete theater script contract: script.json.

    This is a documented JSON contract, not a shared Python type: a reader outside this package
    need not import asg_stagecraft, so every field here is meant to be read from the file itself.
    """

    contract_version: str = "1"
    title: str = Field(min_length=1)
    language: str
    script_method: ScriptMethod
    cast_heading: str = Field(min_length=1)
    act_label: str = Field(min_length=1)
    scene_label: str = Field(min_length=1)
    cast: list[PlayCastMember] = Field(default_factory=list)
    acts: list[ActScript] = Field(min_length=1)


class ActMetrics(BaseModel):
    """Record observed act size and staging without defining a target."""

    chapter_id: ModelId
    scenes: int = Field(ge=0)
    events: int = Field(ge=0)
    lines: int = Field(default=0, ge=0)
    dialogue_lines: int = Field(default=0, ge=0)
    direction_lines: int = Field(default=0, ge=0)
    words: int = Field(default=0, ge=0)


class CharacterStageMetrics(BaseModel):
    """Record how much stage time one character received, across the whole script."""

    character_id: ModelId
    scenes: int = Field(default=0, ge=0)
    lines: int = Field(default=0, ge=0)
    words: int = Field(default=0, ge=0)
    actions: int = Field(default=0, ge=0)


class ScriptMetrics(BaseModel):
    """Record observed theater-script characteristics without budget compliance."""

    narrative_profile: NarrativeProfile
    script_method: ScriptMethod
    words: int = Field(ge=0)
    acts: int = Field(ge=0)
    scenes: int = Field(ge=0)
    events: int = Field(ge=0)
    lines: int = Field(default=0, ge=0)
    dialogue_lines: int = Field(default=0, ge=0)
    direction_lines: int = Field(default=0, ge=0)
    dialogue_words: int = Field(default=0, ge=0)
    direction_words: int = Field(default=0, ge=0)
    setting_words: int = Field(default=0, ge=0)
    dialogue_word_ratio: float = Field(default=0.0, ge=0.0, le=1.0)
    words_per_dialogue_line: float = Field(default=0.0, ge=0.0)
    words_per_direction: float = Field(default=0.0, ge=0.0)
    idle_cast: int = Field(default=0, ge=0)
    absent_participants: int = Field(default=0, ge=0)
    act_metrics: list[ActMetrics] = Field(default_factory=list)
    character_metrics: list[CharacterStageMetrics] = Field(default_factory=list)
