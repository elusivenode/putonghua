import json
import sqlite3
from pathlib import Path

from putonghua.database.migrations import migrate_database
from putonghua.database.repositories import (
    ProjectRepository,
    SourceCreateRecord,
    SourceRepository,
    TranscriptSegmentRecord,
)
from putonghua.models.candidates import CandidateDraft
from putonghua.models.chunks import StudyChunkView
from putonghua.services.candidate_extraction import CandidateExtractionService
from putonghua.services.study_chunks import StudyChunkService


class _FakeProvider:
    def extract_candidates(self, chunk: StudyChunkView) -> list[CandidateDraft]:
        assert chunk.text == "今天我们聊跑步。"
        return [
            CandidateDraft(
                candidate_type="phrase",
                simplified="跑步",
                traditional="跑步",
                pinyin="pao3 bu4",
                english="to run; running",
                rationale="High-frequency verb phrase from the chunk.",
                source_excerpt="今天我们聊跑步。",
            )
        ]


def test_candidate_extraction_service_persists_chunk_link(tmp_path: Path) -> None:
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
                title="Episode 24",
                content_hash="hash-2",
                original_path="https://youtube.com/watch?v=xyz999",
                external_id="xyz999",
                channel_name="Tea with Mona",
                published_at="20260711",
                media_path="/tmp/episode.webm",
                transcript_source="subtitles",
                transcript_text="今天我们聊跑步。",
                metadata={"id": "xyz999"},
            ),
            [TranscriptSegmentRecord(0.0, 30.0, "今天我们聊跑步。", 0)],
        )
        connection.commit()

    chunk_service = StudyChunkService(database_path=database_path)
    build_result = chunk_service.build_for_source(source_id)
    chunk_id = build_result.chunk_ids[0]

    service = CandidateExtractionService(
        database_path=database_path,
        provider=_FakeProvider(),
    )
    result = service.extract_for_chunk(chunk_id)

    assert result.chunk_id == chunk_id
    assert result.candidate_count == 1
    assert len(result.candidate_ids) == 1

    with sqlite3.connect(database_path) as connection:
        row = connection.execute(
            """
            SELECT
                project_id,
                source_id,
                study_chunk_id,
                candidate_type,
                status,
                simplified,
                traditional,
                pinyin,
                english,
                provenance_json
            FROM candidate_cards
            WHERE id = ?
            """,
            (result.candidate_ids[0],),
        ).fetchone()

    assert row is not None
    assert row[0] is not None
    assert row[1] == source_id
    assert row[2] == chunk_id
    assert row[3] == "phrase"
    assert row[4] == "proposed"
    assert row[5] == "跑步"
    provenance = json.loads(str(row[9]))
    assert provenance["chunk_id"] == chunk_id
    assert provenance["candidate_type"] == "phrase"
    assert provenance["source_excerpt"] == "今天我们聊跑步。"
