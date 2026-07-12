ALTER TABLE candidate_cards ADD COLUMN study_chunk_id TEXT REFERENCES study_chunks(id);
