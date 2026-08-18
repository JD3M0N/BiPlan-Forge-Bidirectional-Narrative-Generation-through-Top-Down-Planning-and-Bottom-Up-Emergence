CREATE TABLE IF NOT EXISTS taxonomy_profile (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    family TEXT NOT NULL,
    profile_json TEXT NOT NULL,
    content_hash TEXT NOT NULL
);

CREATE VIRTUAL TABLE IF NOT EXISTS taxonomy_fts USING fts5(
    id UNINDEXED,
    name,
    aliases,
    definition,
    signals
);
