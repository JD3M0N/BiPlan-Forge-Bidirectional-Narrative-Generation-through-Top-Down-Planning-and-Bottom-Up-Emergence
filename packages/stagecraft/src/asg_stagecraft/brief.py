"""A story described as a structured brief instead of one free-text prompt.

StageCraft collects the plot, the cast and a few details as separate fields; to_prompt() turns
them into one deterministic Spanish prompt, and that prompt goes through the analyst exactly
like any other. StoryRequest does not change, nor does the schema sent to the model: a brief run
is a run with a particular prompt, which keeps it comparable with every other run.

What a prompt alone cannot guarantee is the cast. Named characters usually survive the analyst,
but TD-1 already watched one disappear, so missing_cast() checks the characters a run minted
against the ones declared, and the pipeline asks the character designer once more for any that
went missing.

The brief carries neither the profile nor the point of view: the profile travels in the run's
options, and the point of view must never reach a stage before the narration.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .planning.skeleton_match import normalize
from .schemas import CharactersArtifact
from .stage.names import resolve_character

CastRole = Literal["", "protagonista", "antagonista", "aliado", "secundario"]
Pronoun = Literal["", "ella", "él", "elle"]

# A cast this size already strains an Expansive plan; more would be names nobody can stage.
MAX_CAST = 10

# How each declared role reads in the English repair instruction the character designer gets.
_ROLE_IN_ENGLISH = {
    "protagonista": "protagonist",
    "antagonista": "antagonist",
    "aliado": "ally",
    "secundario": "supporting character",
}


def _one_line(value: str) -> str:
    """Collapse the whitespace of a free-text field into single spaces."""
    return " ".join(value.split())


def _closed(text: str) -> str:
    """End a sentence with a full stop unless it already ends with a stop of its own."""
    return text if text[-1:] in ".!?…" else f"{text}."


class CastMember(BaseModel):
    """One character the author declares, by the name the story must keep."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(min_length=1, max_length=80)
    role: CastRole = ""
    pronoun: Pronoun = ""
    description: str = Field(default="", max_length=600)
    secret: str = Field(default="", max_length=400)

    @field_validator("name", "description", "secret")
    @classmethod
    def single_line(cls, value: str) -> str:
        """Collapse whitespace so the composed prompt stays one line per character."""
        return _one_line(value)

    @field_validator("name")
    @classmethod
    def named(cls, value: str) -> str:
        """Reject a name that is only whitespace."""
        if not value:
            raise ValueError("Cada personaje necesita un nombre.")
        return value

    def prompt_line(self) -> str:
        """Describe this character in one line of the composed prompt."""
        line = self.name
        if self.pronoun:
            line += f" ({self.pronoun})"
        if self.role:
            line += f", {self.role}"
        if self.description:
            line += f": {_closed(self.description)}"
        else:
            line = _closed(line)
        if self.secret:
            line += f" Secreto: {_closed(self.secret)}"
        return line


class StoryBrief(BaseModel):
    """The plot, the cast and the details an author fills in, as StageCraft collects them."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    plot: str = Field(min_length=1, max_length=4000)
    title: str = Field(default="", max_length=120)
    genre: str = Field(default="", max_length=80)
    setting: str = Field(default="", max_length=400)
    cast: list[CastMember] = Field(default_factory=list, max_length=MAX_CAST)
    notes: str = Field(default="", max_length=1500)

    @field_validator("title", "genre", "setting")
    @classmethod
    def single_line(cls, value: str) -> str:
        """Collapse the whitespace of the one-line fields."""
        return _one_line(value)

    @field_validator("plot", "notes")
    @classmethod
    def trimmed(cls, value: str) -> str:
        """Trim the free-text fields, keeping the author's own line breaks inside them."""
        return value.strip()

    @model_validator(mode="after")
    def playable(self) -> StoryBrief:
        """Require a plot and names that cannot be confused with one another."""
        if not self.plot:
            raise ValueError("La trama no puede estar vacía.")
        seen: set[str] = set()
        for member in self.cast:
            key = normalize(member.name)
            if key in seen:
                raise ValueError(f"El reparto repite el nombre «{member.name}».")
            seen.add(key)
        return self

    def to_prompt(self) -> str:
        """Compose the Spanish prompt this brief stands for, the same one every time."""
        lines = ["Escribe una historia a partir de esta ficha."]
        if self.title:
            lines.append(f"Título provisional: {_closed(self.title)}")
        if self.genre:
            lines.append(f"Género: {_closed(self.genre)}")
        if self.setting:
            lines.append(f"Ambientación: {_closed(self.setting)}")
        lines.append(f"Trama: {self.plot}")
        if self.cast:
            lines.append("Reparto (usa exactamente estos nombres, sin traducirlos ni cambiarlos):")
            lines.extend(f"- {member.prompt_line()}" for member in self.cast)
        if self.notes:
            lines.append(f"Notas: {self.notes}")
        return "\n".join(lines)


def missing_cast(brief: StoryBrief, characters: CharactersArtifact) -> list[CastMember]:
    """Return the declared characters the minted cast has nobody for."""
    names = {item.id: item.name for item in characters.characters}
    return [member for member in brief.cast if not resolve_character(member.name, names)]


def cast_repair_feedback(missing: list[CastMember]) -> str:
    """Tell the character designer, in English, which declared characters it left out."""
    lines = [
        "",
        "",
        "CAST REPAIR REQUIRED:",
        "The author's brief declares characters this cast is missing. Return a complete "
        "replacement cast that keeps every character you already had and adds each missing one "
        "with exactly this name, untranslated and unchanged:",
    ]
    for member in missing:
        role = _ROLE_IN_ENGLISH.get(member.role, "")
        detail = f" ({role})" if role else ""
        described = f": {member.description}" if member.description else ""
        lines.append(f"- {member.name}{detail}{described}")
    return "\n".join(lines)
