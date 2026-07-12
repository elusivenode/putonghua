CREATE TABLE review_suggestions (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    study_chunk_id TEXT NOT NULL,
    source_message_id TEXT,
    suggestion_index INTEGER NOT NULL,
    candidate_type TEXT NOT NULL,
    simplified TEXT NOT NULL,
    traditional TEXT NOT NULL,
    pinyin TEXT NOT NULL,
    english TEXT NOT NULL,
    rationale TEXT NOT NULL,
    source_excerpt TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'suggested',
    promoted_candidate_card_id TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (conversation_id) REFERENCES review_conversations(id),
    FOREIGN KEY (study_chunk_id) REFERENCES study_chunks(id),
    FOREIGN KEY (source_message_id) REFERENCES review_messages(id),
    FOREIGN KEY (promoted_candidate_card_id) REFERENCES candidate_cards(id),
    UNIQUE (conversation_id, suggestion_index)
);

CREATE INDEX ix_review_suggestions_study_chunk_id
ON review_suggestions(study_chunk_id);

CREATE INDEX ix_review_suggestions_promoted_candidate_card_id
ON review_suggestions(promoted_candidate_card_id);
