"""Loading and validation for versioned narrative taxonomies."""

import json
import re
import unicodedata
from pathlib import Path

from pydantic import BaseModel, Field

from .config import find_project_root


class NarrativeArchetype(BaseModel):
    id: str
    name: str
    spanish_aliases: list[str] = Field(min_length=1)
    description: str
    selection_signals: list[str]
    characteristic_conflict: str
    suggested_progression: list[str] = Field(min_length=3)
    common_beats: list[str] = Field(min_length=3)
    frequent_roles: list[str]
    variants: list[str]
    incompatibilities: list[str]
    influences: list[str]


class CharacterRole(BaseModel):
    id: str
    name: str
    spanish_aliases: list[str] = Field(min_length=1)
    description: str
    drives: list[str]
    strengths: list[str]
    shadows: list[str]
    plot_functions: list[str]
    influence: str = "Jungian-inspired contemporary archetype"


class TaxonomyRepository:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or find_project_root() / "Taxonomies"
        self._archetypes = self._load_collection(
            "Narrative_Archetypes", NarrativeArchetype
        )
        self._roles = self._load_collection("Roles", CharacterRole)

    def _load_collection(self, directory: str, schema: type[BaseModel]) -> dict[str, BaseModel]:
        folder = self.root / directory
        index = json.loads((folder / "index.json").read_text(encoding="utf-8"))
        entries: dict[str, BaseModel] = {}
        for item_id in index["entries"]:
            item = schema.model_validate_json(
                (folder / f"{item_id}.json").read_text(encoding="utf-8")
            )
            if item.id != item_id or item.id in entries:
                raise ValueError(f"Invalid or duplicate taxonomy id: {item_id}")
            entries[item.id] = item
        return entries

    @property
    def archetypes(self) -> list[NarrativeArchetype]:
        return list(self._archetypes.values())

    @property
    def roles(self) -> list[CharacterRole]:
        return list(self._roles.values())

    def get_archetypes(self, ids: list[str]) -> list[NarrativeArchetype]:
        try:
            return [self._archetypes[item_id] for item_id in ids]
        except KeyError as exc:
            raise ValueError(f"Unknown narrative archetype: {exc.args[0]}") from exc

    def recommend_archetypes(self, prompt: str, limit: int = 8) -> list[NarrativeArchetype]:
        """Return a compact lexical shortlist, with a diverse fallback catalog."""
        normalized = unicodedata.normalize("NFKD", prompt.casefold())
        words = set(re.findall(r"[a-z0-9]+", normalized.encode("ascii", "ignore").decode()))
        scored: list[tuple[int, int, NarrativeArchetype]] = []
        for index, item in enumerate(self.archetypes):
            searchable = " ".join([item.name, *item.spanish_aliases, *item.selection_signals])
            searchable = unicodedata.normalize("NFKD", searchable.casefold()).encode("ascii", "ignore").decode()
            score = sum(1 for token in words if len(token) > 3 and token in searchable)
            scored.append((score, -index, item))
        matches = [row for row in scored if row[0] > 0]
        if not matches:
            fallback = ["quest", "mystery", "transformation", "love", "underdog", "discovery", "fall", "comedy"]
            return self.get_archetypes(fallback[:limit])
        return [row[2] for row in sorted(matches, reverse=True)[:limit]]

    def resolve_archetype(self, value: str) -> NarrativeArchetype:
        needle = value.casefold()
        for item in self.archetypes:
            if needle in {item.id.casefold(), item.name.casefold(), *(x.casefold() for x in item.spanish_aliases)}:
                return item
        raise ValueError(f"Unknown narrative archetype: {value}")

    def validate_role_ids(self, ids: list[str]) -> None:
        unknown = set(ids) - self._roles.keys()
        if unknown:
            raise ValueError(f"Unknown Jungian role(s): {', '.join(sorted(unknown))}")
