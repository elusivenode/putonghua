CREATE TABLE transcription_windows (
    id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    window_index INTEGER NOT NULL,
    start_seconds REAL NOT NULL,
    end_seconds REAL NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    attempt_count INTEGER NOT NULL DEFAULT 0,
    transcript_text TEXT,
    model TEXT,
    prompt TEXT,
    last_error TEXT,
    completed_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (source_id) REFERENCES sources(id),
    UNIQUE(source_id, window_index),
    CHECK(status IN ('pending', 'in_progress', 'completed', 'failed'))
);

CREATE INDEX ix_transcription_windows_source_status
ON transcription_windows(source_id, status, window_index);

CREATE UNIQUE INDEX idx_study_chunks_source_chunk_index
ON study_chunks(source_id, chunk_index);
