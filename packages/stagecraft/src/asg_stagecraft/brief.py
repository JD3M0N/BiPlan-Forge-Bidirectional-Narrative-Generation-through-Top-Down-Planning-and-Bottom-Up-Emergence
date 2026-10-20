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

# The label an interface shows for each role and pronoun a cast member may declare.
ROLE_LABELS: dict[CastRole, str] = {
    "": "Sin rol",
    "protagonista": "Protagonista",
    "antagonista": "Antagonista",
    "aliado": "Aliado",
    "secundario": "Secundario",
}
PRONOUN_LABELS: dict[Pronoun, str] = {
    "": "—",
    "ella": "ella",
    "él": "él",
    "elle": "elle",
}

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


def _opened(text: str) -> str:
    """Drop the one full stop _closed would add back, keeping an ellipsis whole."""
    return text[:-1] if text.endswith(".") and not text.endswith("..") else text


_BRIEF_HEADER = "Escribe una historia a partir de esta ficha."
_CAST_HEADER = "Reparto ("
_ONE_LINE_LABELS = {"Título provisional": "title", "Género": "genre", "Ambientación": "setting"}
_BLOCK_LABELS = {"Trama": "plot", "Notas": "notes"}
_PRONOUNS = {"ella", "él", "elle"}
_ROLES = {"protagonista", "antagonista", "aliado", "secundario"}


def _cast_member(line: str) -> CastMember | None:
    """Read one cast line of a composed brief back into the member it describes."""
    head, _, secret = line.partition(" Secreto: ")
    name, _, description = head.partition(": ")
    if not description:
        name = _opened(name)
    role = ""
    name, comma, maybe_role = name.rpartition(", ")
    if not comma:
        name = maybe_role
    elif maybe_role in _ROLES:
        role = maybe_role
    else:
        name = f"{name}, {maybe_role}"
    pronoun = ""
    if name.endswith(")") and " (" in name:
        bare, _, inside = name[:-1].rpartition(" (")
        if inside in _PRONOUNS:
            name, pronoun = bare, inside
    try:
        return CastMember(
            name=name,
            role=role,
            pronoun=pronoun,
            description=_opened(description),
            secret=_opened(secret),
        )
    except ValueError:
        return None


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

    @classmethod
    def from_prompt(cls, prompt: str) -> StoryBrief | None:
        """Read back a brief from the prompt to_prompt composes, or None for any other prompt.

        Added in 7.20. The 7.19 islands runs pasted a composed brief as a free prompt, so the
        author's cast and plot never reached the agents as canon: the cabin boy came back a
        carpenter, the cook a surgeon, and every secret was gone.
        """
        lines = [line.rstrip() for line in prompt.strip().splitlines()]
        if not lines or lines[0].strip() != _BRIEF_HEADER:
            return None
        fields: dict[str, object] = {}
        cast: list[CastMember] = []
        current = ""
        for line in lines[1:]:
            label, _, value = line.partition(": ")
            if label in _ONE_LINE_LABELS and value:
                fields[_ONE_LINE_LABELS[label]] = _opened(value.strip())
                current = ""
            elif label in _BLOCK_LABELS:
                current = _BLOCK_LABELS[label]
                fields[current] = value
            elif line.startswith(_CAST_HEADER):
                current = "cast"
            elif current == "cast" and line.startswith("- "):
                member = _cast_member(line[2:])
                if member is None:
                    return None
                cast.append(member)
            elif current in _BLOCK_LABELS.values():
                fields[current] = f"{fields[current]}\n{line}"
        if not fields.get("plot"):
            return None
        try:
            return cls.model_validate({**fields, "cast": cast})
        except ValueError:
            return None

    def to_prompt(self) -> str:
        """Compose the Spanish prompt this brief stands for, the same one every time."""
        lines = [_BRIEF_HEADER]
        if self.title:
            lines.append(f"Título provisional: {_closed(self.title)}")
        if self.genre:
            lines.append(f"Género: {_closed(self.genre)}")
        if self.setting:
            lines.append(f"Ambientación: {_closed(self.setting)}")
        lines.append(f"Trama: {self.plot}")
        if self.cast:
            lines.append(
                f"{_CAST_HEADER}usa exactamente estos nombres, sin traducirlos ni cambiarlos):"
            )
            lines.extend(f"- {member.prompt_line()}" for member in self.cast)
        if self.notes:
            lines.append(f"Notas: {self.notes}")
        return "\n".join(lines)


def authored_cast_block(brief: StoryBrief | None) -> str:
    """Hand the cast the author wrote, verbatim, to the agents that build characters (7.13).

    Those agents read only the analyst's summary, and in the 7.12 navigators run it kept the
    names and dropped the rest: the astronomer came back a surgeon, the fourteen-year-old cabin
    boy a gunner of fifty, and every declared secret was replaced. Empty without a declared
    cast, so a free-prompt run sends the same prompt as before.
    """
    if brief is None or not brief.cast:
        return ""
    lines = [
        "",
        "",
        "AUTHOR'S CAST (canonical):",
        "The author declared these characters. Keep each one's name, gender, age, trade, "
        "temperament and secret exactly as written here; build on them, never replace them.",
    ]
    lines.extend(f"- {member.prompt_line()}" for member in brief.cast)
    return "\n".join(lines)


def authored_plot_block(brief: StoryBrief | None) -> str:
    """Hand the plot the author wrote, verbatim, to the planner and the plan critic (7.14).

    The planner read only the analyst's summary: in the 7.12 navigators run it planned no ascent,
    no split in the crew and a happy ending for a plot that asked for an open one with a price.
    Empty without a brief, so a free-prompt run sends the same prompt as before.
    """
    if brief is None:
        return ""
    notes = f"\nAuthor's notes: {brief.notes}" if brief.notes else ""
    return (
        "\n\nAUTHOR'S PLOT (canonical):\n"
        "The author wrote this plot. Every turn it names must happen in some event, in its "
        "order, and the ending must be the kind of ending it asks for.\n"
        f"{brief.plot}{notes}"
    )


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
