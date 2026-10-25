"""The cast the character designer wrote, with their names and their ties."""

from __future__ import annotations

from pydantic import (
    BaseModel,
    Field,
    ValidationInfo,
    field_validator,
    model_validator,
)

from ..planning.catalog_types import FunctionalRole, ModelId


class NameOption(BaseModel):
    """One name the character designer could give a character, and how typical it is (7.17)."""

    name: str = Field(min_length=1)
    typicality: float = Field(
        ge=0.0,
        le=1.0,
        description="0 for a name you would rarely reach for, 1 for the first that comes to mind.",
    )


class CharacterProfile(BaseModel):
    """Represent CharacterProfile data and behavior."""

    id: ModelId
    name: str = Field(min_length=1)
    role: str
    goal: str
    motivation: str
    conflict: str
    arc: str
    voice: str
    functional_role: str = ""
    persona: str = ""
    # Asked of the designer and read once by planning/names.py, which keeps the least typical
    # acceptable one (7.17). Never serialized: characters.json and every prompt see the choice.
    name_options: list[NameOption] = Field(
        default_factory=list,
        exclude=True,
        description=(
            "Three different names that fit this character and the world, each with its "
            "typicality; name repeats one of them."
        ),
    )

    @field_validator("functional_role", "persona", mode="before")
    @classmethod
    def normalize_optional_label(cls, value: object, info: ValidationInfo) -> str:
        """Normalize optional role vocabulary and blank values outside the catalog."""
        if not isinstance(value, str):
            return ""
        normalized = value.strip().casefold().replace(" ", "_").replace("-", "_")
        if info.field_name == "functional_role" and normalized:
            if normalized not in {role.value for role in FunctionalRole}:
                return ""
        return normalized


class CharacterRelationship(BaseModel):
    """Represent CharacterRelationship data and behavior."""

    source_character_id: ModelId
    target_character_id: ModelId
    description: str = Field(min_length=1)


class CharactersArtifact(BaseModel):
    """Represent CharactersArtifact data and behavior."""

    characters: list[CharacterProfile] = Field(min_length=1)
    relationships: list[CharacterRelationship] = Field(default_factory=list)

    @model_validator(mode="after")
    def references_are_valid(self) -> CharactersArtifact:
        """Handle the references are valid operation for CharactersArtifact."""
        ids = [item.id for item in self.characters]
        names = [item.name.casefold().strip() for item in self.characters]
        if len(ids) != len(set(ids)) or len(names) != len(set(names)):
            raise ValueError("character ids and names must be unique")
        known = set(ids)
        for relationship in self.relationships:
            refs = {
                relationship.source_character_id,
                relationship.target_character_id,
            }
            if refs - known:
                raise ValueError("character relationships reference unknown characters")
            if len(refs) != 2:
                raise ValueError("character relationships cannot be self-referential")
        return self
