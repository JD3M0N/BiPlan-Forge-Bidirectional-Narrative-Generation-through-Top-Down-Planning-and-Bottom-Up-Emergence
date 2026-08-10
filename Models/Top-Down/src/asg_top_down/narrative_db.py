"""Reproducible SQLite catalog and hybrid narrative-schema retrieval."""

from __future__ import annotations

from dataclasses import dataclass
from contextlib import closing
import hashlib
import json
import math
from pathlib import Path
import sqlite3
from typing import Protocol

from pydantic import BaseModel, Field

from .config import find_project_root
from .schemas import StoryRequest


KINDS = ("macroplot", "situation", "character_arc", "beat", "genre", "role")


class CatalogEntry(BaseModel):
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


class RetrievalTrace(BaseModel):
    query: str
    embedding_model: str | None = None
    used_embeddings: bool = False
    selections: dict[str, list[CatalogEntry]]


class NarrativeBlueprint(BaseModel):
    macroplots: list[CatalogEntry]
    situations: list[CatalogEntry]
    character_arcs: list[CatalogEntry]
    beats: list[CatalogEntry]
    genres: list[CatalogEntry]
    roles: list[CatalogEntry]
    trace: RetrievalTrace


class EmbeddingProvider(Protocol):
    embedding_model_name: str

    def embed_query(self, text: str) -> list[float]: ...

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...


@dataclass(frozen=True)
class _Ranked:
    entry: CatalogEntry
    lexical: float
    semantic: float

    @property
    def score(self) -> float:
        return .4 * self.lexical + .6 * self.semantic


def _cosine(left: list[float], right: list[float]) -> float:
    if not left or len(left) != len(right):
        return 0.0
    denominator = math.sqrt(sum(x * x for x in left)) * math.sqrt(sum(x * x for x in right))
    return 0.0 if not denominator else max(0.0, sum(a * b for a, b in zip(left, right)) / denominator)


class NarrativeSchemaRepository:
    """Owns migrations, seed loading, embedding cache and diversified retrieval."""

    def __init__(self, db_path: Path | None = None, *, provider: EmbeddingProvider | None = None,
                 schema_root: Path | None = None) -> None:
        project = find_project_root()
        repository_schema_root = project / "Models" / "Top-Down" / "schema_db"
        packaged_schema_root = Path(__file__).with_name("schema_db")
        self.schema_root = schema_root or (
            repository_schema_root if repository_schema_root.is_dir() else packaged_schema_root
        )
        self.db_path = db_path or project / ".cache" / "narrative-schemas.sqlite3"
        self.provider = provider if all(hasattr(provider, x) for x in ("embed_query", "embed_documents")) else None
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
            self._seed(db)

    def _seed(self, db: sqlite3.Connection) -> None:
        document = json.loads((self.schema_root / "seeds" / "catalog.json").read_text(encoding="utf-8"))
        for item in document["entries"]:
            db.execute(
                "INSERT INTO catalog_entry(id,kind,name,description,signals_json,compatible_json,provenance) "
                "VALUES(?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET kind=excluded.kind,name=excluded.name,"
                "description=excluded.description,signals_json=excluded.signals_json,"
                "compatible_json=excluded.compatible_json,provenance=excluded.provenance",
                (item["id"], item["kind"], item["name"], item["description"],
                 json.dumps(item.get("signals", []), ensure_ascii=False),
                 json.dumps(item.get("compatible", []), ensure_ascii=False), item["provenance"]),
            )
            db.execute("DELETE FROM catalog_fts WHERE id=?", (item["id"],))
            db.execute("INSERT INTO catalog_fts(id,name,description,signals) VALUES(?,?,?,?)",
                       (item["id"], item["name"], item["description"], " ".join(item.get("signals", []))))
            beat = item.get("beat")
            if beat:
                db.execute(
                    "INSERT INTO beat VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET "
                    "narrative_function=excluded.narrative_function,participants_json=excluded.participants_json,"
                    "preconditions_json=excluded.preconditions_json,effects_json=excluded.effects_json,"
                    "emotional_change=excluded.emotional_change,tension=excluded.tension,"
                    "variants_json=excluded.variants_json,transitions_json=excluded.transitions_json",
                    (item["id"], beat["function"], json.dumps(beat["participants"]),
                     json.dumps(beat["preconditions"]), json.dumps(beat["effects"]),
                     beat["emotional_change"], beat["tension"], json.dumps(beat["variants"]),
                     json.dumps(beat["transitions"])),
                )

    def entries(self, kind: str | None = None) -> list[CatalogEntry]:
        sql = "SELECT c.*, b.narrative_function,b.participants_json,b.preconditions_json,b.effects_json,b.emotional_change,b.tension,b.variants_json,b.transitions_json FROM catalog_entry c LEFT JOIN beat b ON b.id=c.id"
        params: tuple = ()
        if kind:
            sql += " WHERE c.kind=?"
            params = (kind,)
        with closing(self._connect()) as db:
            rows = db.execute(sql, params).fetchall()
        result = []
        for row in rows:
            beat = None
            if row["narrative_function"]:
                beat = {"function": row["narrative_function"], "participants": json.loads(row["participants_json"]),
                        "preconditions": json.loads(row["preconditions_json"]), "effects": json.loads(row["effects_json"]),
                        "emotional_change": row["emotional_change"], "tension": row["tension"],
                        "variants": json.loads(row["variants_json"]), "transitions": json.loads(row["transitions_json"])}
            result.append(CatalogEntry(id=row["id"], kind=row["kind"], name=row["name"],
                description=row["description"], signals=json.loads(row["signals_json"]),
                compatible=json.loads(row["compatible_json"]), provenance=row["provenance"], beat=beat))
        return result

    def _document_vectors(self, entries: list[CatalogEntry]) -> tuple[str | None, dict[str, list[float]]]:
        if not self.provider:
            return None, {}
        model = self.provider.embedding_model_name
        vectors: dict[str, list[float]] = {}
        missing: list[CatalogEntry] = []
        with closing(self._connect()) as db, db:
            for entry in entries:
                key = hashlib.sha256(f"{model}\0{entry.retrieval_text()}".encode()).hexdigest()
                row = db.execute("SELECT vector_json FROM embedding_cache WHERE cache_key=?", (key,)).fetchone()
                if row:
                    vectors[entry.id] = json.loads(row[0])
                else:
                    missing.append(entry)
            if missing:
                embedded = self.provider.embed_documents([x.retrieval_text() for x in missing])
                for entry, vector in zip(missing, embedded):
                    key = hashlib.sha256(f"{model}\0{entry.retrieval_text()}".encode()).hexdigest()
                    db.execute("INSERT OR REPLACE INTO embedding_cache(cache_key,model,vector_json) VALUES(?,?,?)",
                               (key, model, json.dumps(vector)))
                    vectors[entry.id] = vector
        return model, vectors

    @staticmethod
    def _lexical(query: str, entry: CatalogEntry) -> float:
        query_tokens = {x for x in ''.join(ch.casefold() if ch.isalnum() else ' ' for ch in query).split() if len(x) > 2}
        document = entry.retrieval_text().casefold()
        return min(1.0, sum(1 for token in query_tokens if token in document) / max(1, min(5, len(query_tokens))))

    def _fts_scores(self, query: str) -> dict[str, float]:
        tokens = [x for x in ''.join(ch.casefold() if ch.isalnum() else ' ' for ch in query).split() if len(x) > 2]
        if not tokens:
            return {}
        expression = " OR ".join(f'"{token}"' for token in tokens)
        try:
            with closing(self._connect()) as db:
                rows = db.execute("SELECT id, bm25(catalog_fts) AS rank FROM catalog_fts WHERE catalog_fts MATCH ?",
                                  (expression,)).fetchall()
        except sqlite3.OperationalError:
            return {}
        if not rows:
            return {}
        # FTS5 ranks better matches with more-negative values; bound for fusion.
        strengths = {row["id"]: max(0.0, -float(row["rank"])) for row in rows}
        maximum = max(strengths.values(), default=0.0)
        return {key: (value / maximum if maximum else 1.0) for key, value in strengths.items()}

    def retrieve(self, story_request: StoryRequest, limits: dict[str, int] | None = None) -> NarrativeBlueprint:
        limits = limits or {"macroplot": 2, "situation": 2, "character_arc": 2, "beat": 8, "genre": 2, "role": 4}
        query = " ".join((story_request.original_prompt, story_request.premise, story_request.genre, story_request.tone))
        entries = self.entries()
        fts_scores = self._fts_scores(query)
        try:
            model, vectors = self._document_vectors(entries)
        except Exception:
            # Retrieval remains available through FTS5/BM25 when embeddings are offline.
            model, vectors = None, {}
        query_vector: list[float] = []
        if vectors and self.provider:
            try:
                query_vector = self.provider.embed_query(query)
            except Exception:
                vectors = {}
        selections: dict[str, list[CatalogEntry]] = {}
        for kind in KINDS:
            candidates = [entry for entry in entries if entry.kind == kind]
            ranked = [_Ranked(entry, max(self._lexical(query, entry), fts_scores.get(entry.id, 0.0)),
                              _cosine(query_vector, vectors.get(entry.id, []))) for entry in candidates]
            ranked.sort(key=lambda row: (-row.score, row.entry.id))
            chosen: list[CatalogEntry] = []
            for row in ranked:
                # Avoid near duplicate compatible variants unless the catalog is small.
                if any(row.entry.id in x.compatible and x.id in row.entry.compatible for x in chosen) and len(ranked) > limits[kind]:
                    continue
                chosen.append(row.entry.model_copy(update={"score": row.score}))
                if len(chosen) == min(limits[kind], len(candidates)):
                    break
            selections[kind] = chosen
        trace = RetrievalTrace(query=query, embedding_model=model, used_embeddings=bool(query_vector), selections=selections)
        return NarrativeBlueprint(
            macroplots=selections["macroplot"], situations=selections["situation"],
            character_arcs=selections["character_arc"], beats=selections["beat"],
            genres=selections["genre"], roles=selections["role"], trace=trace,
        )
