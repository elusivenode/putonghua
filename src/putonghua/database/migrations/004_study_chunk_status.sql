ALTER TABLE study_chunks ADD COLUMN status TEXT NOT NULL DEFAULT 'pending';
ALTER TABLE study_chunks ADD COLUMN last_reviewed_at TEXT;
ALTER TABLE study_chunks ADD COLUMN notes TEXT;
