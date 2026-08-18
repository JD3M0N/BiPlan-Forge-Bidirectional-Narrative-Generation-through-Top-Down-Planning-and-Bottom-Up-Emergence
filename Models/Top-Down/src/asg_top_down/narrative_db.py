"""Versioned taxonomy profiles, SQLite persistence, and hybrid retrieval."""

from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import re
import sqlite3
import unicodedata
from typing import Literal, Protocol

from pydantic import BaseModel, Field, HttpUrl, model_validator

from .config import find_project_root
from .schemas import StoryRequest, TaxonomyApplication, TaxonomyBrief, TaxonomyOptionReference


KINDS = ("macroplot", "situation", "character_arc", "beat", "genre", "role")
Importance = Literal["core", "common", "optional"]


class CatalogEntry(BaseModel):
    """Legacy v3 catalog entry retained for artifact compatibility."""

    id: str
    kind: str
    name: str
    description: str
    signals: list[str] = Field(default_factory=list)
    compatible: list[str] = Field(default_factory=list)
    provenance: str
    score: float = 0.0
    beat: dict | None = None

    def retrieval_text(self) -> str:
        return f"{self.name}. {self.description}. {'; '.join(self.signals)}"


class TaxonomyOption(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]*$")
    name: str = Field(min_length=2)
    description: str = Field(min_length=12)
    importance: Importance = "optional"


class TaxonomyRole(TaxonomyOption):
    variations: list[str] = Field(min_length=2)


class TaxonomyMovement(TaxonomyOption):
    alternatives: list[str] = Field(min_length=2)
    likely_after: list[str] = Field(default_factory=list)


class TaxonomyNeighbor(BaseModel):
    taxonomy_id: str
    distinction: str = Field(min_length=12)


class TaxonomyVariationAxis(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]*$")
    question: str = Field(min_length=8)
    options: list[str] = Field(min_length=2)


class TaxonomySource(BaseModel):
    title: str
    author_or_organization: str
    url: HttpUrl
    accessed_on: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    contribution: str = Field(min_length=12)


class TaxonomyProfile(BaseModel):
    schema_version: int = Field(default=1, ge=1)
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]*$")
    name: str = Field(min_length=3)
    family: str = Field(min_length=3)
    definition: str = Field(min_length=24)
    aliases: list[str] = Field(min_length=2)
    positive_signals: list[str] = Field(min_length=3)
    negative_signals: list[str] = Field(min_length=2)
    diagnostic_questions: list[str] = Field(min_length=2)
    neighbors: list[TaxonomyNeighbor] = Field(default_factory=list)
    reader_promises: list[TaxonomyOption] = Field(min_length=2)
    roles: list[TaxonomyRole] = Field(min_length=3)
    conflicts: list[str] = Field(min_length=2)
    stakes: list[str] = Field(min_length=2)
    settings: list[str] = Field(min_length=2)
    motifs: list[str] = Field(min_length=2)
    movements: list[TaxonomyMovement] = Field(min_length=4)
    complications: list[TaxonomyOption] = Field(min_length=3)
    twists: list[TaxonomyOption] = Field(min_length=2)
    conclusions: list[TaxonomyOption] = Field(min_length=3)
    variation_axes: list[TaxonomyVariationAxis] = Field(min_length=2)
    subversions: list[str] = Field(min_length=2)
    cliches_to_avoid: list[str] = Field(min_length=2)
    quality_checks: list[str] = Field(min_length=3)
    compatible_accents: list[str] = Field(default_factory=list)
    incompatible_with: list[str] = Field(default_factory=list)
    sources: list[TaxonomySource] = Field(min_length=2)

    @model_validator(mode="after")
    def unique_option_ids(self) -> "TaxonomyProfile":
        options = [
            *self.reader_promises, *self.roles, *self.movements,
            *self.complications, *self.twists, *self.conclusions,
        ]
        ids = [item.id for item in options]
        if len(ids) != len(set(ids)):
            raise ValueError(f"taxonomy {self.id} contains duplicate option IDs")
        movement_ids = {item.id for item in self.movements}
        unknown = {value for item in self.movements for value in item.likely_after} - movement_ids
        if unknown:
            raise ValueError(f"taxonomy {self.id} references unknown movement IDs: {sorted(unknown)}")
        return self

    def option(self, option_id: str) -> TaxonomyOption:
        for option in (
            *self.reader_promises, *self.roles, *self.movements,
            *self.complications, *self.twists, *self.conclusions,
        ):
            if option.id == option_id:
                return option
        raise KeyError(option_id)

    def retrieval_text(self) -> str:
        neighbors = " ".join(item.distinction for item in self.neighbors)
        return " ".join((
            self.name, " ".join(self.aliases), self.definition,
            " ".join(self.positive_signals), " ".join(self.negative_signals),
            neighbors, " ".join(self.conflicts), " ".join(self.motifs),
        ))


class TaxonomyCandidate(BaseModel):
    profile: TaxonomyProfile
    score: float = Field(ge=0, le=1)
    lexical_score: float = Field(ge=0, le=1)
    semantic_score: float | None = Field(default=None, ge=0, le=1)
    matched_terms: list[str] = Field(default_factory=list)
    explicit_match: bool = False


class RetrievalTrace(BaseModel):
    query: str
    embedding_model: str | None = None
    used_embeddings: bool = False
    candidates: list[TaxonomyCandidate] = Field(default_factory=list)
    selections: dict[str, list[CatalogEntry]] = Field(default_factory=dict)


class NarrativeBlueprint(BaseModel):
    """V3.1 taxonomy shortlist plus optional fields used when reading v3 artifacts."""

    candidates: list[TaxonomyCandidate] = Field(default_factory=list)
    trace: RetrievalTrace
    macroplots: list[CatalogEntry] = Field(default_factory=list)
    situations: list[CatalogEntry] = Field(default_factory=list)
    character_arcs: list[CatalogEntry] = Field(default_factory=list)
    beats: list[CatalogEntry] = Field(default_factory=list)
    genres: list[CatalogEntry] = Field(default_factory=list)
    roles: list[CatalogEntry] = Field(default_factory=list)

    def model_context(self) -> dict:
        """Return taxonomy content without retrieval lexicon matches or diagnostic traces."""
        if self.candidates:
            return {
                "candidates": [{
                    "profile": item.profile.model_dump(mode="json"),
                    "score": item.score,
                    "explicit_match": item.explicit_match,
                } for item in self.candidates]
            }
        return self.model_dump(mode="json", exclude={"trace"})


class EmbeddingProvider(Protocol):
    embedding_model_name: str

    def embed_query(self, text: str) -> list[float]: ...
    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...


@dataclass(frozen=True)
class _Ranked:
    profile: TaxonomyProfile
    lexical: float
    semantic: float
    matched_terms: tuple[str, ...]
    explicit: bool

    @property
    def score(self) -> float:
        if self.explicit:
            return 1.0
        if self.semantic:
            return min(1.0, .4 * self.lexical + .6 * self.semantic)
        return self.lexical


def _cosine(left: list[float], right: list[float]) -> float:
    if not left or len(left) != len(right):
        return 0.0
    denominator = math.sqrt(sum(x * x for x in left)) * math.sqrt(sum(x * x for x in right))
    return 0.0 if not denominator else max(0.0, sum(a * b for a, b in zip(left, right)) / denominator)


def _normalize(value: str) -> str:
    value = unicodedata.normalize("NFKD", value.casefold())
    value = value.encode("ascii", "ignore").decode("ascii")
    return " ".join(re.findall(r"[a-z0-9]+", value))


class NarrativeSchemaRepository:
    """Own taxonomy migrations, seed reconciliation, embeddings, and retrieval."""

    def __init__(self, db_path: Path | None = None, *, provider: EmbeddingProvider | None = None,
                 schema_root: Path | None = None) -> None:
        project = find_project_root()
        repository_schema_root = project / "Models" / "Top-Down" / "schema_db"
        packaged_schema_root = Path(__file__).with_name("schema_db")
        self.schema_root = schema_root or (
            repository_schema_root if repository_schema_root.is_dir() else packaged_schema_root
        )
        self.db_path = db_path or project / ".cache" / "narrative-schemas.sqlite3"
        self.provider = provider if all(
            hasattr(provider, name) for name in ("embed_query", "embed_documents")
        ) else None
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialize(self) -> None:
        with closing(self._connect()) as db, db:
            db.execute("CREATE TABLE IF NOT EXISTS schema_migration(version TEXT PRIMARY KEY)")
            for migration in sorted((self.schema_root / "migrations").glob("*.sql")):
                if db.execute("SELECT 1 FROM schema_migration WHERE version=?", (migration.name,)).fetchone():
                    continue
                db.executescript(migration.read_text(encoding="utf-8"))
                db.execute("INSERT INTO schema_migration(version) VALUES (?)", (migration.name,))
            self._seed_legacy(db)
            self._seed_taxonomies(db)

    def _seed_legacy(self, db: sqlite3.Connection) -> None:
        seed = self.schema_root / "seeds" / "catalog.json"
        if not seed.is_file():
            return
        document = json.loads(seed.read_text(encoding="utf-8"))
        for item in document.get("entries", []):
            db.execute(
                "INSERT INTO catalog_entry(id,kind,name,description,signals_json,compatible_json,provenance) "
                "VALUES(?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET kind=excluded.kind,name=excluded.name,"
                "description=excluded.description,signals_json=excluded.signals_json,"
                "compatible_json=excluded.compatible_json,provenance=excluded.provenance",
                (item["id"], item["kind"], item["name"], item["description"],
                 json.dumps(item.get("signals", []), ensure_ascii=False),
                 json.dumps(item.get("compatible", []), ensure_ascii=False), item["provenance"]),
            )

    def _seed_taxonomies(self, db: sqlite3.Connection) -> None:
        folder = self.schema_root / "taxonomies"
        manifest_path = folder / "manifest.json"
        if not manifest_path.is_file():
            return
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        ids = manifest["profiles"]
        if len(ids) != len(set(ids)):
            raise ValueError("taxonomy manifest contains duplicate IDs")
        profiles: list[TaxonomyProfile] = []
        for taxonomy_id in ids:
            profile = TaxonomyProfile.model_validate_json(
                (folder / f"{taxonomy_id}.json").read_text(encoding="utf-8")
            )
            if profile.id != taxonomy_id:
                raise ValueError(f"taxonomy manifest ID does not match profile: {taxonomy_id}")
            profiles.append(profile)
        expected = set(ids)
        for row in db.execute("SELECT id FROM taxonomy_profile").fetchall():
            if row["id"] not in expected:
                db.execute("DELETE FROM taxonomy_profile WHERE id=?", (row["id"],))
                db.execute("DELETE FROM taxonomy_fts WHERE id=?", (row["id"],))
        for profile in profiles:
            payload = profile.model_dump_json()
            fingerprint = hashlib.sha256(payload.encode()).hexdigest()
            db.execute(
                "INSERT INTO taxonomy_profile(id,name,family,profile_json,content_hash) VALUES(?,?,?,?,?) "
                "ON CONFLICT(id) DO UPDATE SET name=excluded.name,family=excluded.family,"
                "profile_json=excluded.profile_json,content_hash=excluded.content_hash",
                (profile.id, profile.name, profile.family, payload, fingerprint),
            )
            db.execute("DELETE FROM taxonomy_fts WHERE id=?", (profile.id,))
            db.execute(
                "INSERT INTO taxonomy_fts(id,name,aliases,definition,signals) VALUES(?,?,?,?,?)",
                (profile.id, profile.name, " ".join(profile.aliases), profile.definition,
                 " ".join(profile.positive_signals)),
            )

    def profiles(self) -> list[TaxonomyProfile]:
        with closing(self._connect()) as db:
            rows = db.execute("SELECT profile_json FROM taxonomy_profile ORDER BY id").fetchall()
        return [TaxonomyProfile.model_validate_json(row[0]) for row in rows]

    def profile(self, taxonomy_id: str) -> TaxonomyProfile:
        with closing(self._connect()) as db:
            row = db.execute(
                "SELECT profile_json FROM taxonomy_profile WHERE id=?", (taxonomy_id,)
            ).fetchone()
        if row is None:
            raise ValueError(f"unknown taxonomy profile: {taxonomy_id}")
        return TaxonomyProfile.model_validate_json(row[0])

    def entries(self, kind: str | None = None) -> list[CatalogEntry]:
        sql = "SELECT * FROM catalog_entry"
        params: tuple = ()
        if kind:
            sql += " WHERE kind=?"
            params = (kind,)
        with closing(self._connect()) as db:
            rows = db.execute(sql, params).fetchall()
        return [CatalogEntry(
            id=row["id"], kind=row["kind"], name=row["name"], description=row["description"],
            signals=json.loads(row["signals_json"]), compatible=json.loads(row["compatible_json"]),
            provenance=row["provenance"],
        ) for row in rows]

    def _recognition_lexicon(self) -> dict[str, list[str]]:
        path = self.schema_root / "seeds" / "recognition_lexicon.json"
        if not path.is_file():
            return {}
        raw = json.loads(path.read_text(encoding="utf-8"))
        return {key: [_normalize(value) for value in values] for key, values in raw.items()}

    def _document_vectors(self, profiles: list[TaxonomyProfile]) -> tuple[str | None, dict[str, list[float]]]:
        if not self.provider:
            return None, {}
        model = self.provider.embedding_model_name
        vectors: dict[str, list[float]] = {}
        missing: list[TaxonomyProfile] = []
        with closing(self._connect()) as db, db:
            for profile in profiles:
                fingerprint = profile.model_dump_json()
                key = hashlib.sha256(f"{model}\0{fingerprint}".encode()).hexdigest()
                row = db.execute("SELECT vector_json FROM embedding_cache WHERE cache_key=?", (key,)).fetchone()
                if row:
                    vectors[profile.id] = json.loads(row[0])
                else:
                    missing.append(profile)
            if missing:
                embedded = self.provider.embed_documents([item.retrieval_text() for item in missing])
                for profile, vector in zip(missing, embedded):
                    fingerprint = profile.model_dump_json()
                    key = hashlib.sha256(f"{model}\0{fingerprint}".encode()).hexdigest()
                    db.execute(
                        "INSERT OR REPLACE INTO embedding_cache(cache_key,model,vector_json) VALUES(?,?,?)",
                        (key, model, json.dumps(vector)),
                    )
                    vectors[profile.id] = vector
        return model, vectors

    @staticmethod
    def _lexical(
        query: str,
        evidence_query: str,
        profile: TaxonomyProfile,
        recognition: list[str],
    ) -> tuple[float, list[str], bool]:
        normalized = _normalize(query)
        evidence = f" {_normalize(evidence_query)} "
        phrases = [_normalize(profile.name), *(_normalize(value) for value in profile.aliases), *recognition]
        matched = sorted({phrase for phrase in phrases if phrase and f" {phrase} " in evidence})
        explicit = bool(matched)
        query_tokens = {token for token in normalized.split() if len(token) > 2}
        document = _normalize(profile.retrieval_text())
        overlap = sum(1 for token in query_tokens if re.search(rf"\b{re.escape(token)}\b", document))
        score = min(1.0, overlap / max(1, min(7, len(query_tokens))))
        if explicit:
            score = 1.0
        return score, matched, explicit

    def _taxonomy_fts_scores(self, query: str) -> dict[str, float]:
        tokens = [token for token in _normalize(query).split() if len(token) > 2]
        if not tokens:
            return {}
        expression = " OR ".join(f'"{token}"' for token in tokens)
        try:
            with closing(self._connect()) as db:
                rows = db.execute(
                    "SELECT id, bm25(taxonomy_fts) AS rank FROM taxonomy_fts "
                    "WHERE taxonomy_fts MATCH ?", (expression,),
                ).fetchall()
        except sqlite3.OperationalError:
            return {}
        strengths = {row["id"]: max(0.0, -float(row["rank"])) for row in rows}
        maximum = max(strengths.values(), default=0.0)
        return {
            taxonomy_id: (strength / maximum if maximum else 1.0)
            for taxonomy_id, strength in strengths.items()
        }

    def retrieve(self, story_request: StoryRequest, limits: dict[str, int] | None = None) -> NarrativeBlueprint:
        del limits  # v3 compatibility; v3.1 returns a shortlist of at most three profiles.
        query = " ".join(filter(None, (
            story_request.processed_prompt, story_request.genre,
            story_request.premise, story_request.tone,
        )))
        evidence_query = story_request.original_prompt
        profiles = self.profiles()
        if not profiles:
            return self._retrieve_legacy(story_request)
        lexicon = self._recognition_lexicon()
        fts_scores = self._taxonomy_fts_scores(query)
        try:
            model, vectors = self._document_vectors(profiles)
        except Exception:
            model, vectors = None, {}
        query_vector: list[float] = []
        if vectors and self.provider:
            try:
                query_vector = self.provider.embed_query(query)
            except Exception:
                vectors = {}
        ranked: list[_Ranked] = []
        for profile in profiles:
            lexical, matched, explicit = self._lexical(
                query, evidence_query, profile, lexicon.get(profile.id, []),
            )
            lexical = max(lexical, fts_scores.get(profile.id, 0.0))
            ranked.append(_Ranked(
                profile, lexical, _cosine(query_vector, vectors.get(profile.id, [])),
                tuple(matched), explicit,
            ))
        ranked.sort(key=lambda item: (-item.score, not item.explicit, item.profile.id))
        candidates = [TaxonomyCandidate(
            profile=item.profile, score=item.score, lexical_score=item.lexical,
            semantic_score=item.semantic if query_vector else None,
            matched_terms=list(item.matched_terms), explicit_match=item.explicit,
        ) for item in ranked[:3]]
        trace = RetrievalTrace(
            query=query, embedding_model=model, used_embeddings=bool(query_vector), candidates=candidates,
        )
        return NarrativeBlueprint(candidates=candidates, trace=trace)

    def _retrieve_legacy(self, story_request: StoryRequest) -> NarrativeBlueprint:
        entries = self.entries()
        query = " ".join(filter(None, (
            story_request.processed_prompt, story_request.premise,
            story_request.genre, story_request.tone,
        )))
        selections: dict[str, list[CatalogEntry]] = {}
        for kind in KINDS:
            candidates = [entry for entry in entries if entry.kind == kind]
            candidates.sort(
                key=lambda entry: -sum(
                    token in _normalize(entry.retrieval_text())
                    for token in set(_normalize(query).split())
                )
            )
            selections[kind] = candidates[:{"beat": 8, "role": 4}.get(kind, 2)]
        trace = RetrievalTrace(query=query, selections=selections)
        return NarrativeBlueprint(
            trace=trace, macroplots=selections["macroplot"], situations=selections["situation"],
            character_arcs=selections["character_arc"], beats=selections["beat"],
            genres=selections["genre"], roles=selections["role"],
        )

    @staticmethod
    def _profiles_from_blueprint(blueprint: NarrativeBlueprint) -> dict[str, TaxonomyProfile]:
        return {candidate.profile.id: candidate.profile for candidate in blueprint.candidates}

    def validate_application(self, application: TaxonomyApplication,
                             blueprint: NarrativeBlueprint) -> None:
        profiles = self._profiles_from_blueprint(blueprint)
        if application.primary_taxonomy_id not in profiles:
            raise ValueError("primary taxonomy was not retrieved")
        if application.accent_taxonomy_id:
            candidate = next(
                (item for item in blueprint.candidates
                 if item.profile.id == application.accent_taxonomy_id), None
            )
            if candidate is None or not candidate.explicit_match:
                raise ValueError("accent taxonomy requires explicit prompt evidence")
            primary = profiles[application.primary_taxonomy_id]
            if application.accent_taxonomy_id in primary.incompatible_with:
                raise ValueError("selected taxonomy accent is incompatible with the primary taxonomy")
            if (primary.compatible_accents
                    and application.accent_taxonomy_id not in primary.compatible_accents):
                raise ValueError("selected taxonomy accent is not listed as compatible")

        def validate_group(references, attribute: str) -> None:
            for reference in references:
                profile = profiles.get(reference.taxonomy_id)
                allowed = set() if profile is None else {
                    item.id for item in getattr(profile, attribute)
                }
                if reference.option_id not in allowed:
                    raise ValueError(
                        f"unknown {attribute} option: "
                        f"{reference.taxonomy_id}:{reference.option_id}"
                    )

        validate_group(application.selected_promises, "reader_promises")
        validate_group(application.selected_roles, "roles")
        validate_group(application.selected_movements, "movements")
        validate_group(application.selected_complications, "complications")
        validate_group([application.selected_conclusion], "conclusions")
        if application.selected_twist:
            validate_group([application.selected_twist], "twists")
        for reference in application.omitted_conventions:
            profile = profiles.get(reference.taxonomy_id)
            if profile is None:
                raise ValueError(f"unknown taxonomy: {reference.taxonomy_id}")
            profile.option(reference.option_id)

    def compile_brief(self, application: TaxonomyApplication,
                      blueprint: NarrativeBlueprint) -> TaxonomyBrief:
        self.validate_application(application, blueprint)
        profiles = self._profiles_from_blueprint(blueprint)

        def description(reference: TaxonomyOptionReference) -> str:
            option = profiles[reference.taxonomy_id].option(reference.option_id)
            return f"{option.name}: {option.description}"

        primary = profiles[application.primary_taxonomy_id]
        accent = profiles.get(application.accent_taxonomy_id or "")
        checks = list(primary.quality_checks)
        avoid = list(primary.cliches_to_avoid)
        if accent:
            checks.extend(accent.quality_checks[:2])
            avoid.extend(accent.cliches_to_avoid[:1])
        return TaxonomyBrief(
            primary_taxonomy=primary.name,
            accent_taxonomy=accent.name if accent else None,
            reader_promises=[description(item) for item in application.selected_promises],
            roles=[description(item) for item in application.selected_roles],
            movements=[description(item) for item in application.selected_movements],
            complications=[description(item) for item in application.selected_complications],
            twist=description(application.selected_twist) if application.selected_twist else None,
            conclusion=description(application.selected_conclusion),
            freshness_choices=application.freshness_choices,
            quality_checks=list(dict.fromkeys(checks)),
            avoid=list(dict.fromkeys(avoid)),
        )
