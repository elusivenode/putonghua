import sqlite3
from pathlib import Path

from putonghua.database.migrations import migrate_database


def test_migrate_database_applies_initial_schema(tmp_path: Path) -> None:
    database_path = tmp_path / "putonghua.db"

    applied = migrate_database(database_path)

    assert applied == [
        "001_initial",
        "002_youtube_import",
        "003_study_chunks",
        "004_study_chunk_status",
        "005_candidate_cards_by_chunk",
        "006_candidate_card_type",
        "007_review_conversations",
        "008_review_suggestions",
        "009_publication_record_uniqueness",
    ]

    with sqlite3.connect(database_path) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }

    assert "schema_migrations" in tables
    assert "projects" in tables
    assert "sources" in tables
    assert "candidate_cards" in tables
    assert "candidate_scores" in tables
    assert "review_decisions" in tables
    assert "publication_records" in tables
    assert "learner_profiles" in tables
    assert "workflow_runs" in tables
    assert "transcript_segments" in tables
    assert "study_chunks" in tables
    assert "review_conversations" in tables
    assert "review_messages" in tables
    assert "review_suggestions" in tables

    with sqlite3.connect(database_path) as connection:
        columns = {
            row[1] for row in connection.execute("PRAGMA table_info(candidate_cards)")
        }

    assert "study_chunk_id" in columns
    assert "candidate_type" in columns


def test_migrate_database_is_idempotent(tmp_path: Path) -> None:
    database_path = tmp_path / "putonghua.db"

    first_run = migrate_database(database_path)
    second_run = migrate_database(database_path)

    assert first_run == [
        "001_initial",
        "002_youtube_import",
        "003_study_chunks",
        "004_study_chunk_status",
        "005_candidate_cards_by_chunk",
        "006_candidate_card_type",
        "007_review_conversations",
        "008_review_suggestions",
        "009_publication_record_uniqueness",
    ]
    assert second_run == []
