CREATE TABLE tutorial_sessions (
    id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    current_step TEXT NOT NULL,
    project_id TEXT,
    source_id TEXT,
    study_chunk_id TEXT,
    review_conversation_id TEXT,
    review_suggestion_id TEXT,
    candidate_card_id TEXT,
    publication_record_id TEXT,
    completed_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX idx_tutorial_sessions_active
ON tutorial_sessions(status)
WHERE status = 'active';
