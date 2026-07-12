from pathlib import Path

from putonghua.database.connection import connect
from putonghua.database.migrations import migrate_database
from putonghua.database.repositories import (
    CandidateCardCreateRecord,
    CandidateRepository,
    ProjectRepository,
    PublicationRecordRepository,
    SourceCreateRecord,
    SourceRepository,
    TranscriptSegmentRecord,
)
from putonghua.models.anki import AnkiPublishNoteRequest, AnkiPublishNoteResult
from putonghua.services.candidate_publish import (
    CandidatePublishConfig,
    CandidatePublishService,
)


class _FakeAnkiPublishProvider:
    def __init__(self) -> None:
        self.requests: list[AnkiPublishNoteRequest] = []

    def publish_note(self, request: AnkiPublishNoteRequest) -> AnkiPublishNoteResult:
        self.requests.append(request)
        return AnkiPublishNoteResult(note_id=42001)


def test_candidate_publish_service_publishes_and_is_idempotent(tmp_path: Path) -> None:
    database_path = tmp_path / "putonghua.db"
    migrate_database(database_path)

    with connect(database_path) as connection:
        project = ProjectRepository(connection).get_or_create_by_name("Podcast Project")
        source_id = SourceRepository(connection).create_source(
            SourceCreateRecord(
                project_id=project.id,
                source_type="youtube_audio",
                title="Episode 27",
                content_hash="hash-5",
                original_path="https://youtube.com/watch?v=publish001",
                external_id="publish001",
                channel_name="Tea with Mona",
                published_at="20260712",
                media_path="/tmp/episode.webm",
                transcript_source="subtitles",
                transcript_text="大家好",
                metadata={"id": "publish001"},
            ),
            [TranscriptSegmentRecord(0.0, 2.0, "大家好", 0)],
        )
        connection.execute(
            """
            INSERT INTO study_chunks(
                id,
                source_id,
                chunk_index,
                start_seconds,
                end_seconds,
                text,
                transcript_segment_count,
                char_count,
                status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("chunk-1", source_id, 0, 0.0, 2.0, "大家好", 1, 3, "completed"),
        )
        candidate_id = CandidateRepository(connection).create_candidates(
            [
                CandidateCardCreateRecord(
                    project_id=project.id,
                    source_id=source_id,
                    study_chunk_id="chunk-1",
                    candidate_type="phrase",
                    simplified="大家好",
                    traditional="大家好",
                    pinyin="da4 jia1 hao3",
                    english="hello everyone",
                    provenance={"origin": "test"},
                    status="promoted",
                )
            ]
        )[0]
        connection.commit()

    provider = _FakeAnkiPublishProvider()
    service = CandidatePublishService(
        database_path=database_path,
        provider=provider,
        config=CandidatePublishConfig(
            deck_name="Mandarin",
            note_type_name="Mandarin vocab",
            publish_tags=["putonghua-test"],
        ),
    )

    first_result = service.publish_candidate(candidate_id)
    second_result = service.publish_candidate(candidate_id)

    assert first_result.candidate_id == candidate_id
    assert first_result.anki_note_id == 42001
    assert first_result.status == "published"
    assert first_result.created is True
    assert second_result.publication_record_id == first_result.publication_record_id
    assert second_result.anki_note_id == 42001
    assert second_result.created is False
    assert len(provider.requests) == 1
    assert provider.requests[0].deck_name == "Mandarin"
    assert provider.requests[0].note_type_name == "Mandarin vocab"
    assert provider.requests[0].fields["Hanzi"] == "大家好"
    assert provider.requests[0].fields["Audio"] == ""

    with connect(database_path) as connection:
        candidate = CandidateRepository(connection).get_candidate(candidate_id)
        publication = PublicationRecordRepository(connection).get_by_candidate_id(
            candidate_id
        )

    assert candidate is not None
    assert candidate.status == "published"
    assert publication is not None
    assert publication.putonghua_id == candidate_id
    assert publication.anki_note_id == "42001"
    assert publication.status == "published"


def test_candidate_publish_service_requires_promoted_candidate(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "putonghua.db"
    migrate_database(database_path)

    with connect(database_path) as connection:
        project = ProjectRepository(connection).get_or_create_by_name("Podcast Project")
        source_id = SourceRepository(connection).create_source(
            SourceCreateRecord(
                project_id=project.id,
                source_type="youtube_audio",
                title="Episode 28",
                content_hash="hash-6",
                original_path="https://youtube.com/watch?v=publish002",
                external_id="publish002",
                channel_name="Tea with Mona",
                published_at="20260712",
                media_path="/tmp/episode.webm",
                transcript_source="subtitles",
                transcript_text="你好",
                metadata={"id": "publish002"},
            ),
            [TranscriptSegmentRecord(0.0, 2.0, "你好", 0)],
        )
        connection.execute(
            """
            INSERT INTO study_chunks(
                id,
                source_id,
                chunk_index,
                start_seconds,
                end_seconds,
                text,
                transcript_segment_count,
                char_count,
                status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("chunk-1", source_id, 0, 0.0, 2.0, "你好", 1, 2, "completed"),
        )
        candidate_id = CandidateRepository(connection).create_candidates(
            [
                CandidateCardCreateRecord(
                    project_id=project.id,
                    source_id=source_id,
                    study_chunk_id="chunk-1",
                    candidate_type="word",
                    simplified="你好",
                    traditional="你好",
                    pinyin="ni3 hao3",
                    english="hello",
                    provenance={"origin": "test"},
                    status="proposed",
                )
            ]
        )[0]
        connection.commit()

    service = CandidatePublishService(
        database_path=database_path,
        provider=_FakeAnkiPublishProvider(),
        config=CandidatePublishConfig(
            deck_name="Mandarin",
            note_type_name="Mandarin vocab",
            publish_tags=["putonghua-test"],
        ),
    )

    try:
        service.publish_candidate(candidate_id)
    except ValueError as exc:
        assert "not publishable" in str(exc)
    else:
        raise AssertionError("Expected ValueError for unpublished candidate status")
