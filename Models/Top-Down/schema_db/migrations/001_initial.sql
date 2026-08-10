PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS catalog_entry (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL CHECK (kind IN ('macroplot','situation','character_arc','beat','genre','role')),
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    signals_json TEXT NOT NULL,
    compatible_json TEXT NOT NULL DEFAULT '[]',
    provenance TEXT NOT NULL,
    embedding_model TEXT,
    embedding_json TEXT
);

CREATE TABLE IF NOT EXISTS beat (
    id TEXT PRIMARY KEY REFERENCES catalog_entry(id) ON DELETE CASCADE,
    narrative_function TEXT NOT NULL,
    participants_json TEXT NOT NULL,
    preconditions_json TEXT NOT NULL,
    effects_json TEXT NOT NULL,
    emotional_change TEXT NOT NULL,
    tension INTEGER NOT NULL CHECK (tension BETWEEN 1 AND 10),
    variants_json TEXT NOT NULL,
    transitions_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS embedding_cache (
    cache_key TEXT PRIMARY KEY,
    model TEXT NOT NULL,
    vector_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE VIRTUAL TABLE IF NOT EXISTS catalog_fts USING fts5(
    id UNINDEXED, name, description, signals
);
