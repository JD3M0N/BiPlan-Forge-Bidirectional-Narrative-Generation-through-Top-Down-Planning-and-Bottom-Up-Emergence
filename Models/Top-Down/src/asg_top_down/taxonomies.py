"""Loading and validation for versioned narrative taxonomies."""

import json
import math
import re
import unicodedata
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from .config import find_project_root

if TYPE_CHECKING:
    from .provider import LanguageModelProvider


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


class ArchetypeMatch(BaseModel):
    """Auditable relevance score for a narrative archetype."""

    archetype_id: str
    score: float = Field(ge=0, le=1)
    lexical_score: float = Field(ge=0, le=1)
    semantic_score: float | None = Field(default=None, ge=0, le=1)
    matched_terms: list[str]
    catalog_order: int = Field(ge=0)


class SemanticArchetypeScore(BaseModel):
    archetype_id: str
    relevance: float = Field(ge=0, le=1)


class SemanticArchetypeRanking(BaseModel):
    scores: list[SemanticArchetypeScore]


class TaxonomyRepository:
    _LEXICAL_WEIGHT = 0.70
    _SEMANTIC_WEIGHT = 0.30
    _FIELD_WEIGHTS = {
        "name": 1.0,
        "spanish_aliases": 1.0,
        "selection_signals": 0.85,
        "variants": 0.65,
        "common_beats": 0.45,
        "description": 0.30,
        "characteristic_conflict": 0.30,
    }

    def __init__(
        self,
        root: Path | None = None,
        provider: "LanguageModelProvider | None" = None,
    ) -> None:
        self.root = root or find_project_root() / "Taxonomies"
        self.provider = provider
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

    @staticmethod
    def _normalize(value: str) -> str:
        value = unicodedata.normalize("NFKD", value.casefold())
        return " ".join(re.findall(r"[a-z0-9]+", value.encode("ascii", "ignore").decode()))

    @classmethod
    def _weighted_fields(cls, item: NarrativeArchetype) -> list[tuple[str, float]]:
        fields: list[tuple[str, float]] = []
        for field_name, weight in cls._FIELD_WEIGHTS.items():
            value = getattr(item, field_name)
            values = value if isinstance(value, list) else [value]
            fields.extend((entry, weight) for entry in values)
        return fields

    def _lexical_scores(self, prompt: str) -> list[ArchetypeMatch]:
        normalized_prompt = self._normalize(prompt)
        prompt_tokens = set(normalized_prompt.split())
        archetypes = self.archetypes

        document_tokens: list[set[str]] = []
        for item in archetypes:
            document_tokens.append({
                token
                for value, _ in self._weighted_fields(item)
                for token in self._normalize(value).split()
                if len(token) >= 3
            })
        document_frequency = {
            token: sum(token in document for document in document_tokens)
            for token in set().union(*document_tokens)
        }
        count = len(archetypes)

        def idf(token: str) -> float:
            return 1.0 + math.log((count + 1) / (document_frequency.get(token, 0) + 1))

        scored: list[ArchetypeMatch] = []
        padded_prompt = f" {normalized_prompt} "
        for index, item in enumerate(archetypes):
            raw_score = 0.0
            matched: set[str] = set()
            counted_tokens: set[tuple[str, str]] = set()
            for value, weight in self._weighted_fields(item):
                phrase = self._normalize(value)
                if not phrase:
                    continue
                phrase_tokens = [token for token in phrase.split() if len(token) >= 3]
                if phrase_tokens and f" {phrase} " in padded_prompt:
                    phrase_idf = sum(idf(token) for token in phrase_tokens) / len(phrase_tokens)
                    raw_score += 1.5 * weight * phrase_idf
                    matched.add(phrase)
                for token in prompt_tokens.intersection(phrase_tokens):
                    evidence_key = (value, token)
                    if evidence_key not in counted_tokens:
                        raw_score += 0.35 * weight * idf(token)
                        counted_tokens.add(evidence_key)
                        matched.add(token)
            lexical_score = 0.0 if not normalized_prompt else 1.0 - math.exp(-raw_score / 3.0)
            scored.append(ArchetypeMatch(
                archetype_id=item.id,
                score=min(1.0, lexical_score),
                lexical_score=min(1.0, lexical_score),
                matched_terms=sorted(matched),
                catalog_order=index,
            ))
        return scored

    def _semantic_scores(self, prompt: str) -> dict[str, float] | None:
        if self.provider is None or not self._normalize(prompt):
            return None
        catalog = [
            {
                "id": item.id,
                "name": item.name,
                "aliases": item.spanish_aliases,
                "description": item.description,
                "signals": item.selection_signals,
                "conflict": item.characteristic_conflict,
                "variants": item.variants,
            }
            for item in self.archetypes
        ]
        expected_ids = set(self._archetypes)
        for _ in range(2):
            try:
                result = self.provider.generate_structured(
                    system_instruction=(
                        "Evalua de forma independiente la relevancia de cada arquetipo narrativo "
                        "para el texto. Devuelve todos los IDs exactamente una vez y asigna a cada "
                        "uno un valor real entre 0 y 1. Los valores no tienen que sumar 1."
                    ),
                    prompt=(
                        f"TEXTO:\n{prompt}\n\nCATALOGO:\n"
                        f"{json.dumps(catalog, ensure_ascii=False, indent=2)}"
                    ),
                    schema=SemanticArchetypeRanking,
                )
                ids = [entry.archetype_id for entry in result.scores]
                if len(ids) != len(expected_ids) or set(ids) != expected_ids:
                    raise ValueError("Semantic ranking must contain every taxonomy exactly once")
                return {entry.archetype_id: entry.relevance for entry in result.scores}
            except Exception:
                continue
        return None

    def score_archetypes(self, prompt: str) -> list[ArchetypeMatch]:
        """Return all archetypes ranked by bounded lexical and semantic relevance."""
        lexical_matches = self._lexical_scores(prompt)
        semantic_scores = self._semantic_scores(prompt)
        scored: list[ArchetypeMatch] = []
        for match in lexical_matches:
            semantic_score = None if semantic_scores is None else semantic_scores[match.archetype_id]
            final_score = (
                match.lexical_score
                if semantic_score is None
                else self._LEXICAL_WEIGHT * match.lexical_score + self._SEMANTIC_WEIGHT * semantic_score
            )
            scored.append(match.model_copy(update={
                "score": min(1.0, max(0.0, final_score)),
                "semantic_score": semantic_score,
            }))
        return sorted(scored, key=lambda row: (-row.score, -row.lexical_score, row.catalog_order))

    def best_archetype_match(self, prompt: str) -> ArchetypeMatch:
        """Return the highest-scoring archetype match."""
        return self.score_archetypes(prompt)[0]

    def recommend_archetypes(self, prompt: str, limit: int = 8) -> list[NarrativeArchetype]:
        """Return a compact lexical shortlist, with a diverse fallback catalog."""
        scored = self.score_archetypes(prompt)
        matches = [row for row in scored if row.score > 0]
        if not matches:
            fallback = ["quest", "mystery", "transformation", "love", "underdog", "discovery", "fall", "comedy"]
            return self.get_archetypes(fallback[:limit])
        return self.get_archetypes([row.archetype_id for row in matches[:limit]])

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
