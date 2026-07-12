import sqlite3
from pathlib import Path

from putonghua.database.migrations import migrate_database
from putonghua.database.repositories import (
    CandidateCardCreateRecord,
    CandidateRepository,
    ProjectRepository,
    ReviewSuggestionRepository,
    SourceCreateRecord,
    SourceRepository,
    TranscriptSegmentRecord,
)
from putonghua.services.chunk_review import ChunkReviewService
from putonghua.services.study_chunks import StudyChunkService
from putonghua.tests_support import FakeReviewProvider


def test_chunk_review_service_persists_conversation(tmp_path: Path) -> None:
    database_path = tmp_path / "putonghua.db"
    migrate_database(database_path)

    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        projects = ProjectRepository(connection)
        sources = SourceRepository(connection)
        candidate_repository = CandidateRepository(connection)
        project = projects.get_or_create_by_name("Podcast Project")
        source_id = sources.create_source(
            SourceCreateRecord(
                project_id=project.id,
                source_type="youtube_audio",
                title="Episode 25",
                content_hash="hash-3",
                original_path="https://youtube.com/watch?v=review001",
                external_id="review001",
                channel_name="Tea with Mona",
                published_at="20260711",
                media_path="/tmp/episode.webm",
                transcript_source="subtitles",
                transcript_text="我会尽量地把每一个字都说出来。",
                metadata={"id": "review001"},
            ),
            [TranscriptSegmentRecord(0.0, 30.0, "我会尽量地把每一个字都说出来。", 0)],
        )
        connection.commit()

    chunk_service = StudyChunkService(database_path=database_path)
    build_result = chunk_service.build_for_source(source_id)
    chunk_id = build_result.chunk_ids[0]

    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        candidate_repository = CandidateRepository(connection)
        candidate_repository.create_candidates(
            [
                CandidateCardCreateRecord(
                    project_id=project.id,
                    source_id=source_id,
                    study_chunk_id=chunk_id,
                    candidate_type="phrase",
                    simplified="尽量",
                    traditional="盡量",
                    pinyin="jǐn liàng",
                    english="to do one's best",
                    provenance={"source_excerpt": "我会尽量地把每一个字都说出来。"},
                )
            ]
        )
        connection.commit()

    service = ChunkReviewService(
        database_path=database_path,
        provider=FakeReviewProvider(),
        provider_name="fake-openai",
        model_name="test-model",
    )

    result = service.chat_for_chunk(chunk_id, "Prefer sentence cards.")

    assert result.assistant_text.startswith("Focus on the phrase")
    assert result.conversation_id
    assert result.suggested_cards[0].candidate_type == "sentence"

    messages = service.list_conversation_messages(result.conversation_id)
    assert len(messages) == 2
    assert messages[0].role == "user"
    assert messages[1].role == "assistant"

    suggestion_views = service.list_review_suggestions(result.conversation_id)
    assert len(suggestion_views) == 1
    assert suggestion_views[0].conversation_id == result.conversation_id
    assert suggestion_views[0].study_chunk_id == chunk_id
    assert suggestion_views[0].candidate_type == "sentence"
    assert suggestion_views[0].status == "suggested"

    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        suggestion_repository = ReviewSuggestionRepository(connection)
        suggestions = suggestion_repository.list_for_conversation(
            result.conversation_id
        )
        chat_candidates = CandidateRepository(connection).list_candidates_for_chunk(
            chunk_id
        )

    assert len(suggestions) == 1
    assert suggestions[0].study_chunk_id == chunk_id
    assert suggestions[0].candidate_type == "sentence"
    assert suggestions[0].simplified == "我会尽量地把每一个字都说出来。"
    assert suggestions[0].status == "suggested"
    assert len(chat_candidates) == 2
    assert chat_candidates[1].candidate_type == "sentence"
