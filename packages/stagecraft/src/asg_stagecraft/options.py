"""Every choice a caller makes about one run, validated in one place.

Before 7.3 each option was threaded by hand through Settings, the facade, the pipeline and every
surface, and a finished run recorded neither its ledger, its guidance nor its audio switch. A run
is now configured by one GenerationOptions: the facade builds it, the pipeline reads it and
persists it as generation_options.json, and every surface - the CLI, the console, the bot and
StageCraft - builds the same object.

Adding an option means adding a validated field here and the matching facade keyword, which a
test keeps in step with these fields.
"""

from __future__ import annotations

from typing import Any

from asg_core import NARRATION_VOICE_NAMES
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .formats import ActorMemory, NarrativeVoice, ScriptMethod, StoryFormat, voice_choice
from .planning.profiles import NarrativeProfile

# The label an interface shows for turns_per_beat's upper bound. The field itself has no ``le``,
# so a CLI or .env value above it still validates: this is only what a picker offers.
MAX_OFFERED_TURNS_PER_BEAT = 16

# The choice an interface shows for an empty audio_voice, which lets the story's language decide.
AUTOMATIC_AUDIO_VOICE_LABEL = "Automática (según el idioma)"


class GenerationOptions(BaseModel):
    """The validated choices of one run, persisted with it as generation_options.json."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    story_format: StoryFormat = StoryFormat.NARRATIVE
    script_method: ScriptMethod = ScriptMethod.NATIVE
    # None lets the analyst infer the profile from the prompt; a value outranks that inference.
    narrative_profile: NarrativeProfile | None = Field(
        default=None,
        title="Perfil narrativo",
        description="La escala de la historia. Automático deja que lo deduzca el analista.",
    )
    narrative_guidance: bool = Field(
        default=True,
        title="Guía de esqueletos",
        description="Inspira el plan con esqueletos de trama clásicos.",
    )
    promise_ledger: bool = Field(
        default=True,
        title="Ledger de promesas",
        description=(
            "Traza qué promete la historia y dónde lo paga. Apagarlo es su brazo de control."
        ),
    )
    audio: bool = Field(
        default=True,
        title="Narración en audio",
        description="Lee la historia terminada en story.mp3.",
    )
    # The edge-tts voice that reads story.mp3; empty lets the story's language choose it.
    audio_voice: str = Field(
        default="",
        title="Voz del audio",
        description="Quién lee la historia. Automática elige por el idioma.",
    )
    narrative_voice: NarrativeVoice = Field(
        default=NarrativeVoice.OMNISCIENT,
        title="Visión",
        description="Desde dónde se cuenta la función: qué turnos y qué pensamientos ve.",
    )
    # The character a voice told from one character follows, as the person typed the name; it
    # is resolved against the cast only once the cast exists. Empty keeps the default narrator.
    narrator: str = Field(
        default="",
        max_length=80,
        title="Personaje de la visión",
        description=(
            "Quién cuenta la historia en las visiones limitada y en primera persona. "
            "Los capítulos que no presencie se omiten."
        ),
    )
    # The register the author asks the narrator for, in their own words. Only the narration of
    # a simulated run reads it, so it can never change the plan, the script or the performance.
    narration_tone: str = Field(
        default="",
        max_length=300,
        title="Tono del narrador",
        description="El registro de la voz que cuenta. Colorea la prosa; nunca añade sucesos.",
    )
    actor_memory: ActorMemory = Field(
        default=ActorMemory.OWN,
        title="Memoria de los actores",
        description="Qué recuerda cada personaje de lo que ocurrió en escena.",
    )
    turns_per_beat: int = Field(
        default=8,
        ge=2,
        title="Turnos por beat",
        description="Cuántos turnos puede durar un beat antes de que el mundo lo cierre.",
    )

    @field_validator("narrator", "narration_tone")
    @classmethod
    def single_line(cls, value: str) -> str:
        """Collapse the whitespace of free text, so a stray newline never reaches a prompt."""
        return " ".join(value.split())

    @field_validator("audio_voice")
    @classmethod
    def known_audio_voice(cls, value: str) -> str:
        """Accept only a narration voice the audio module offers, or none at all."""
        value = value.strip()
        if value and value not in NARRATION_VOICE_NAMES:
            raise ValueError(f"La voz {value!r} no está entre las voces de narración disponibles.")
        return value

    @model_validator(mode="after")
    def narrator_needs_a_voice_told_from_one(self) -> GenerationOptions:
        """Reject a narrator for a voice that is not told from any one character."""
        if self.narrator and not voice_choice(self.narrative_voice).takes_character:
            raise ValueError(
                "Solo las visiones limitada y en primera persona se cuentan desde un "
                "personaje: elige una de ellas o deja vacío el personaje de la visión."
            )
        return self

    @classmethod
    def from_settings(cls, settings: Any, **overrides: Any) -> GenerationOptions:
        """Build options from environment settings, letting explicit choices win.

        An override of None keeps the settings value, so a surface can pass an unset flag
        straight through instead of branching on it.
        """
        values = {
            name: getattr(settings, name) for name in cls.model_fields if hasattr(settings, name)
        }
        values.update({name: value for name, value in overrides.items() if value is not None})
        unknown = sorted(set(values) - set(cls.model_fields))
        if unknown:
            raise TypeError(f"unknown generation options: {', '.join(unknown)}")
        return cls.model_validate(values)

    def with_changes(self, **changes: Any) -> GenerationOptions:
        """Return a validated copy with some choices replaced, rejecting unknown names."""
        unknown = sorted(set(changes) - set(type(self).model_fields))
        if unknown:
            raise TypeError(f"unknown generation options: {', '.join(unknown)}")
        return type(self).model_validate({**self.model_dump(), **changes})
