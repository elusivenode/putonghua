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
from putonghua.services.chunk_review import ChunkReviewService
from putonghua.services.review_suggestions import ReviewSuggestionService
from putonghua.services.study_chunks import StudyChunkService
from putonghua.tests_support import FakeReviewProvider


def test_review_suggestion_service_lists_and_promotes(tmp_path: Path) -> None:
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
                title="Episode 26",
                content_hash="hash-4",
                original_path="https://youtube.com/watch?v=review002",
                external_id="review002",
                channel_name="Tea with Mona",
                published_at="20260711",
                media_path="/tmp/episode.webm",
                transcript_source="subtitles",
                transcript_text="我会尽量地把每一个字都说出来。",
                metadata={"id": "review002"},
            ),
            [TranscriptSegmentRecord(0.0, 30.0, "我会尽量地把每一个字都说出来。", 0)],
        )
        connection.commit()

    chunk_service = StudyChunkService(database_path=database_path)
    chunk_id = chunk_service.build_for_source(source_id).chunk_ids[0]

    review_service = ChunkReviewService(
        database_path=database_path,
        provider=FakeReviewProvider(),
        provider_name="fake-openai",
        model_name="test-model",
    )
    chat_result = review_service.chat_for_chunk(chunk_id, "Prefer sentence cards.")

    service = ReviewSuggestionService(database_path=database_path)
    suggestions = service.list_review_suggestions(chat_result.conversation_id)

    assert len(suggestions) == 1
    suggestion_id = suggestions[0].id
    assert suggestions[0].status == "suggested"

    first_result = service.promote_suggestion(suggestion_id)
    second_result = service.promote_suggestion(suggestion_id)

    assert first_result.suggestion_id == suggestion_id
    assert first_result.status == "promoted"
    assert first_result.created is True
    assert second_result.candidate_id == first_result.candidate_id
    assert second_result.status == "promoted"
    assert second_result.created is False

    with sqlite3.connect(database_path) as connection:
        row = connection.execute(
            """
            SELECT status, simplified, provenance_json
            FROM candidate_cards
            WHERE id = ?
            """,
            (first_result.candidate_id,),
        ).fetchone()
        suggestion_row = connection.execute(
            """
            SELECT status, promoted_candidate_card_id
            FROM review_suggestions
            WHERE id = ?
            """,
            (suggestion_id,),
        ).fetchone()

    assert row is not None
    assert row[0] == "promoted"
    assert row[1] == "我会尽量地把每一个字都说出来。"
    provenance = json.loads(str(row[2]))
    assert provenance["origin"] == "review_suggestion"
    assert provenance["review_suggestion_id"] == suggestion_id

    assert suggestion_row is not None
    assert suggestion_row[0] == "promoted"
    assert suggestion_row[1] == first_result.candidate_id
