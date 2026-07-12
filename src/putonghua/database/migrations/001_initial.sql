CREATE TABLE projects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE learner_profiles (
    id TEXT PRIMARY KEY,
    language TEXT NOT NULL,
    proficiency_estimate TEXT,
    learning_goals TEXT,
    preferred_card_styles TEXT,
    preferred_explanation_style TEXT,
    preferred_voices TEXT,
    topics_of_interest TEXT,
    card_generation_preferences TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE sources (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    source_type TEXT NOT NULL,
    title TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    original_path TEXT,
    imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id)
);

CREATE TABLE candidate_cards (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    source_id TEXT NOT NULL,
    status TEXT NOT NULL,
    simplified TEXT,
    traditional TEXT,
    pinyin TEXT,
    english TEXT,
    provenance_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id),
    FOREIGN KEY (source_id) REFERENCES sources(id)
);

CREATE TABLE candidate_scores (
    candidate_card_id TEXT PRIMARY KEY,
    learning_value_score REAL NOT NULL,
    scoring_factors_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (candidate_card_id) REFERENCES candidate_cards(id)
);

CREATE TABLE review_decisions (
    id TEXT PRIMARY KEY,
    candidate_card_id TEXT NOT NULL,
    decision TEXT NOT NULL,
    notes TEXT,
    decided_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (candidate_card_id) REFERENCES candidate_cards(id)
);

CREATE TABLE publication_records (
    id TEXT PRIMARY KEY,
    candidate_card_id TEXT NOT NULL,
    putonghua_id TEXT NOT NULL UNIQUE,
    anki_note_id TEXT,
    published_at TEXT,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (candidate_card_id) REFERENCES candidate_cards(id)
);

CREATE TABLE workflow_runs (
    id TEXT PRIMARY KEY,
    project_id TEXT,
    run_type TEXT NOT NULL,
    status TEXT NOT NULL,
    started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TEXT,
    error_message TEXT,
    FOREIGN KEY (project_id) REFERENCES projects(id)
);
