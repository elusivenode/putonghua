ALTER TABLE sources ADD COLUMN external_id TEXT;
ALTER TABLE sources ADD COLUMN channel_name TEXT;
ALTER TABLE sources ADD COLUMN published_at TEXT;
ALTER TABLE sources ADD COLUMN media_path TEXT;
ALTER TABLE sources ADD COLUMN transcript_source TEXT;
ALTER TABLE sources ADD COLUMN transcript_text TEXT;
ALTER TABLE sources ADD COLUMN metadata_json TEXT NOT NULL DEFAULT '{}';

CREATE TABLE transcript_segments (
    id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    start_seconds REAL NOT NULL,
    end_seconds REAL NOT NULL,
    text TEXT NOT NULL,
    segment_index INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (source_id) REFERENCES sources(id)
);
