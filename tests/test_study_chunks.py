import sqlite3
from pathlib import Path

from putonghua.database.migrations import migrate_database
from putonghua.database.repositories import (
    ProjectRepository,
    SourceCreateRecord,
    SourceRepository,
    TranscriptSegmentRecord,
)
from putonghua.services.study_chunks import StudyChunkBuildConfig, StudyChunkService


def test_study_chunk_service_builds_chunks(tmp_path: Path) -> None:
    database_path = tmp_path / "putonghua.db"
    migrate_database(database_path)

    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        projects = ProjectRepository(connection)
        sources = SourceRepository(connection)
        project = projects.get_or_create_by_name("Podcast Project")
        source_id = sources.create_source(
            SourceCreateRecord(
                project_id=project.id,
                source_type="youtube_audio",
                title="Episode 23",
                content_hash="hash",
                original_path="https://youtube.com/watch?v=abc123",
                external_id="abc123",
                channel_name="Tea with Mona",
                published_at="20260711",
                media_path="/tmp/episode.webm",
                transcript_source="subtitles",
                transcript_text="one\ntwo\nthree",
                metadata={"id": "abc123"},
            ),
            [
                TranscriptSegmentRecord(0.0, 10.0, "第一句。", 0),
                TranscriptSegmentRecord(10.0, 20.0, "第二句。", 1),
                TranscriptSegmentRecord(20.0, 35.0, "第三句。", 2),
            ],
        )
        connection.commit()

    service = StudyChunkService(database_path=database_path)
    result = service.build_for_source(
        source_id,
        StudyChunkBuildConfig(
            max_duration_seconds=25.0,
            max_char_count=20,
            min_duration_seconds=15.0,
            min_char_count=2,
        ),
    )

    assert result.chunk_count == 2

    with sqlite3.connect(database_path) as connection:
        rows = connection.execute(
            """
            SELECT chunk_index, transcript_segment_count, text
            FROM study_chunks
            WHERE source_id = ?
            ORDER BY chunk_index
            """,
            (source_id,),
        ).fetchall()

    assert rows[0][0] == 0
    assert rows[0][1] == 2
    assert "第一句" in rows[0][2]
    assert rows[1][0] == 1


def test_study_chunk_service_requires_segments(tmp_path: Path) -> None:
    database_path = tmp_path / "putonghua.db"
    migrate_database(database_path)
    service = StudyChunkService(database_path=database_path)

    try:
        service.build_for_source("missing-source")
    except ValueError as exc:
        assert "No transcript segments found" in str(exc)
    else:
        raise AssertionError("Expected ValueError for missing transcript segments")


def test_study_chunk_service_updates_and_reads_status(tmp_path: Path) -> None:
    database_path = tmp_path / "putonghua.db"
    migrate_database(database_path)

    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        projects = ProjectRepository(connection)
        sources = SourceRepository(connection)
        project = projects.get_or_create_by_name("Podcast Project")
        source_id = sources.create_source(
            SourceCreateRecord(
                project_id=project.id,
                source_type="youtube_audio",
                title="Episode 23",
                content_hash="hash",
                original_path="https://youtube.com/watch?v=abc123",
                external_id="abc123",
                channel_name="Tea with Mona",
                published_at="20260711",
                media_path="/tmp/episode.webm",
                transcript_source="subtitles",
                transcript_text="one",
                metadata={"id": "abc123"},
            ),
            [TranscriptSegmentRecord(0.0, 20.0, "第一句。第二句。", 0)],
        )
        connection.commit()

    service = StudyChunkService(database_path=database_path)
    build_result = service.build_for_source(source_id)
    chunk_id = build_result.chunk_ids[0]

    next_chunk = service.get_next_pending_chunk(source_id)
    assert next_chunk is not None
    assert next_chunk.id == chunk_id
    assert next_chunk.status == "pending"

    update_result = service.update_chunk_status(chunk_id, "completed", "done")
    assert update_result.status == "completed"

    updated_chunk = service.get_chunk(chunk_id)
    assert updated_chunk is not None
    assert updated_chunk.status == "completed"
    assert updated_chunk.notes == "done"

    no_pending = service.get_next_pending_chunk(source_id)
    assert no_pending is None
