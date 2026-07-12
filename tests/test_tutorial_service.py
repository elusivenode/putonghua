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
    StudyChunkRecord,
    StudyChunkRepository,
    TranscriptSegmentRecord,
)
from putonghua.services.candidate_promotion import CandidatePromotionService
from putonghua.services.candidate_publish import (
    CandidatePublishConfig,
    CandidatePublishService,
)
from putonghua.services.chunk_review import ChunkReviewService
from putonghua.services.review_suggestions import ReviewSuggestionService
from putonghua.services.tutorial import TutorialService
from putonghua.tests_support import FakeReviewProvider


class _FakeAnkiPublishProvider:
    def publish_note(self, request: object):
        from putonghua.models.anki import AnkiPublishNoteResult

        return AnkiPublishNoteResult(note_id=42001)


def _seed_chunk(database_path: Path) -> tuple[str, str, str]:
    migrate_database(database_path)

    with connect(database_path) as connection:
        project = ProjectRepository(connection).get_or_create_by_name(
            "Tutorial Project"
        )
        source_id = SourceRepository(connection).create_source(
            SourceCreateRecord(
                project_id=project.id,
                source_type="youtube_audio",
                title="Tutorial Episode",
                content_hash="tutorial-source-1",
                original_path="https://youtube.com/watch?v=tutorial001",
                external_id="tutorial001",
                channel_name="Tutorial Channel",
                published_at="20260712",
                media_path="/tmp/tutorial.webm",
                transcript_source="subtitles",
                transcript_text="我们开始吧。",
                metadata={"id": "tutorial001"},
            ),
            [TranscriptSegmentRecord(0.0, 10.0, "我们开始吧。", 0)],
        )
        chunk_id = StudyChunkRepository(connection).replace_for_source(
            source_id,
            [
                StudyChunkRecord(
                    source_id=source_id,
                    chunk_index=0,
                    start_seconds=0.0,
                    end_seconds=10.0,
                    text="我们开始吧。",
                    transcript_segment_count=1,
                    char_count=6,
                    status="pending",
                )
            ],
        )[0]
        connection.commit()

    return project.id, source_id, chunk_id


def test_tutorial_service_bootstraps_dedicated_workspace(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "putonghua.db"
    tutorial_service = TutorialService(database_path)

    session = tutorial_service.ensure_active_session()

    assert session.project_id is not None
    assert session.source_id is not None
    assert session.study_chunk_id is None
    assert session.current_step == "session_layout"
    assert [step.completed for step in session.steps] == [
        False,
        False,
        False,
        False,
        False,
        False,
    ]
    assert session.steps[0].title == "Understand the session layout"
    assert session.steps[0].command == "tutorial next"
    assert session.steps[0].actions[0].startswith("Look at the four main areas")
    assert "navigation first" in session.steps[0].choice_hint

    with connect(database_path) as connection:
        sources = SourceRepository(connection).list_sources_for_project(
            session.project_id
        )
        chunks = StudyChunkRepository(connection).list_chunks_for_source(
            session.source_id
        )

    assert [source.title for source in sources] == ["Putonghua Tutorial: Real Workflow"]
    assert [chunk.status for chunk in chunks] == ["completed", "pending"]
    assert "read the dashboard layout" in session.steps[0].detail


def test_tutorial_service_start_fresh_session_clears_workspace_progress(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "putonghua.db"
    tutorial_service = TutorialService(database_path)

    first = tutorial_service.start_fresh_session()
    tutorial_service.advance_active_session()
    tutorial_service.advance_active_session()

    with connect(database_path) as connection:
        tutorial_source = SourceRepository(connection).get_source_by_content_hash(
            "putonghua-tutorial-sample-v1"
        )
        assert tutorial_source is not None
        pending_chunk = [
            chunk
            for chunk in StudyChunkRepository(connection).list_chunks_for_source(
                tutorial_source.id
            )
            if chunk.status == "pending"
        ][0]
        CandidateRepository(connection).create_candidates(
            [
                CandidateCardCreateRecord(
                    project_id=first.project_id or "",
                    source_id=tutorial_source.id,
                    study_chunk_id=pending_chunk.id,
                    candidate_type="word",
                    simplified="教程",
                    traditional="教程",
                    pinyin="jiao4 cheng2",
                    english="tutorial",
                    provenance={"origin": "tutorial-test"},
                )
            ]
        )
        connection.commit()

    restarted = tutorial_service.start_fresh_session()

    assert restarted.id != first.id
    assert restarted.current_step == "session_layout"
    assert restarted.study_chunk_id is None
    assert [step.completed for step in restarted.steps] == [
        False,
        False,
        False,
        False,
        False,
        False,
    ]

    with connect(database_path) as connection:
        tutorial_source = SourceRepository(connection).get_source_by_content_hash(
            "putonghua-tutorial-sample-v1"
        )
        assert tutorial_source is not None
        chunks = StudyChunkRepository(connection).list_chunks_for_source(
            tutorial_source.id
        )
        assert (
            sum(
                len(CandidateRepository(connection).list_candidates_for_chunk(chunk.id))
                for chunk in chunks
            )
            == 0
        )


def test_tutorial_service_tracks_real_workflow_progress(tmp_path: Path) -> None:
    database_path = tmp_path / "putonghua.db"
    project_id, source_id, chunk_id = _seed_chunk(database_path)

    tutorial_service = TutorialService(database_path)
    session = tutorial_service.ensure_active_session(study_chunk_id=chunk_id)

    assert session.project_id == project_id
    assert session.source_id == source_id
    assert session.study_chunk_id == chunk_id
    assert session.current_step == "candidates_extracted"
    assert [step.completed for step in session.steps] == [
        True,
        True,
        True,
        False,
        False,
        False,
    ]

    with connect(database_path) as connection:
        CandidateRepository(connection).create_candidates(
            [
                CandidateCardCreateRecord(
                    project_id=project_id,
                    source_id=source_id,
                    study_chunk_id=chunk_id,
                    candidate_type="sentence",
                    simplified="我们开始吧。",
                    traditional="我們開始吧。",
                    pinyin="wo3 men kai1 shi3 ba",
                    english="Let's begin.",
                    provenance={"origin": "tutorial-test"},
                )
            ]
        )
        connection.commit()

    session = tutorial_service.refresh_active_session()
    assert session.current_step == "suggestion_promoted"
    assert [step.completed for step in session.steps] == [
        True,
        True,
        True,
        True,
        False,
        False,
    ]

    review_result = ChunkReviewService(
        database_path=database_path,
        provider=FakeReviewProvider(),
        provider_name="fake-openai",
        model_name="test-model",
    ).chat_for_chunk(chunk_id, "Suggest one sentence card.")

    session = tutorial_service.refresh_active_session()
    assert session.current_step == "suggestion_promoted"
    assert session.review_conversation_id == review_result.conversation_id
    assert [step.completed for step in session.steps] == [
        True,
        True,
        True,
        True,
        False,
        False,
    ]

    suggestion = ReviewSuggestionService(database_path).list_review_suggestions(
        review_result.conversation_id
    )[0]
    promotion = ReviewSuggestionService(database_path).promote_suggestion(suggestion.id)

    session = tutorial_service.refresh_active_session()
    assert session.current_step == "candidate_published"
    assert session.review_suggestion_id == suggestion.id
    assert session.candidate_card_id == promotion.candidate_id
    assert [step.completed for step in session.steps] == [
        True,
        True,
        True,
        True,
        True,
        False,
    ]

    CandidatePublishService(
        database_path=database_path,
        provider=_FakeAnkiPublishProvider(),
        config=CandidatePublishConfig(
            deck_name="Mandarin",
            note_type_name="Mandarin vocab",
            publish_tags=["putonghua-test"],
        ),
    ).publish_candidate(promotion.candidate_id)

    session = tutorial_service.refresh_active_session()
    assert session.status == "completed"
    assert session.current_step == "completed"
    assert session.publication_record_id is not None
    assert session.completed_at is not None
    assert [step.completed for step in session.steps] == [
        True,
        True,
        True,
        True,
        True,
        True,
    ]


def test_tutorial_service_allows_direct_promotion_without_chat(tmp_path: Path) -> None:
    database_path = tmp_path / "putonghua.db"
    project_id, source_id, chunk_id = _seed_chunk(database_path)

    tutorial_service = TutorialService(database_path)
    session = tutorial_service.ensure_active_session(study_chunk_id=chunk_id)

    with connect(database_path) as connection:
        candidate_id = CandidateRepository(connection).create_candidates(
            [
                CandidateCardCreateRecord(
                    project_id=project_id,
                    source_id=source_id,
                    study_chunk_id=chunk_id,
                    candidate_type="word",
                    simplified="开始",
                    traditional="開始",
                    pinyin="kai1 shi3",
                    english="to begin",
                    provenance={"origin": "tutorial-test"},
                )
            ]
        )[0]
        connection.commit()

    assert session.current_step == "candidates_extracted"

    CandidatePromotionService(database_path).promote_candidate(candidate_id)

    session = tutorial_service.refresh_active_session()
    assert session.current_step == "candidate_published"
    assert session.candidate_card_id == candidate_id
    assert session.review_suggestion_id is None
    assert [step.completed for step in session.steps] == [
        True,
        True,
        True,
        True,
        True,
        False,
    ]


def test_tutorial_service_resets_and_recreates_active_session(tmp_path: Path) -> None:
    database_path = tmp_path / "putonghua.db"
    _, _, chunk_id = _seed_chunk(database_path)

    tutorial_service = TutorialService(database_path)
    first = tutorial_service.ensure_active_session(study_chunk_id=chunk_id)

    assert tutorial_service.reset_active_session() is True
    assert tutorial_service.get_active_session() is None

    second = tutorial_service.ensure_active_session(study_chunk_id=chunk_id)

    assert second.id != first.id
    assert second.study_chunk_id == chunk_id


def test_tutorial_service_reset_clears_tutorial_workspace(tmp_path: Path) -> None:
    database_path = tmp_path / "putonghua.db"
    tutorial_service = TutorialService(database_path)
    started = tutorial_service.start_fresh_session()
    tutorial_service.advance_active_session()
    tutorial_service.advance_active_session()

    with connect(database_path) as connection:
        tutorial_source = SourceRepository(connection).get_source_by_content_hash(
            "putonghua-tutorial-sample-v1"
        )
        assert tutorial_source is not None
        pending_chunk = [
            chunk
            for chunk in StudyChunkRepository(connection).list_chunks_for_source(
                tutorial_source.id
            )
            if chunk.status == "pending"
        ][0]
        CandidateRepository(connection).create_candidates(
            [
                CandidateCardCreateRecord(
                    project_id=started.project_id or "",
                    source_id=tutorial_source.id,
                    study_chunk_id=pending_chunk.id,
                    candidate_type="word",
                    simplified="教程",
                    traditional="教程",
                    pinyin="jiao4 cheng2",
                    english="tutorial",
                    provenance={"origin": "tutorial-test"},
                )
            ]
        )
        connection.commit()

    assert started.source_id is not None
    assert tutorial_service.reset_active_session() is True

    with connect(database_path) as connection:
        chunks = StudyChunkRepository(connection).list_chunks_for_source(
            started.source_id
        )
        assert (
            sum(
                len(CandidateRepository(connection).list_candidates_for_chunk(chunk.id))
                for chunk in chunks
            )
            == 0
        )


def test_tutorial_service_advances_manual_intro_steps(tmp_path: Path) -> None:
    database_path = tmp_path / "putonghua.db"
    tutorial_service = TutorialService(database_path)

    first = tutorial_service.ensure_active_session()
    second = tutorial_service.advance_active_session()
    third = tutorial_service.advance_active_session()

    assert first.current_step == "session_layout"
    assert second.current_step == "workflow_overview"
    assert third.current_step == "chunk_selected"


def test_tutorial_service_reports_pending_publish_state(tmp_path: Path) -> None:
    database_path = tmp_path / "putonghua.db"
    project_id, source_id, chunk_id = _seed_chunk(database_path)

    tutorial_service = TutorialService(database_path)
    session = tutorial_service.ensure_active_session(study_chunk_id=chunk_id)

    with connect(database_path) as connection:
        CandidateRepository(connection).create_candidates(
            [
                CandidateCardCreateRecord(
                    project_id=project_id,
                    source_id=source_id,
                    study_chunk_id=chunk_id,
                    candidate_type="sentence",
                    simplified="我们开始吧。",
                    traditional="我們開始吧。",
                    pinyin="wo3 men kai1 shi3 ba",
                    english="Let's begin.",
                    provenance={"origin": "tutorial-test"},
                )
            ]
        )
        connection.commit()

    review_result = ChunkReviewService(
        database_path=database_path,
        provider=FakeReviewProvider(),
        provider_name="fake-openai",
        model_name="test-model",
    ).chat_for_chunk(chunk_id, "Suggest one sentence card.")
    suggestion = ReviewSuggestionService(database_path).list_review_suggestions(
        review_result.conversation_id
    )[0]
    promotion = ReviewSuggestionService(database_path).promote_suggestion(suggestion.id)

    with connect(database_path) as connection:
        PublicationRecordRepository(connection).create_publication(
            candidate_id=promotion.candidate_id,
            putonghua_id=promotion.candidate_id,
            status="publishing",
        )
        connection.commit()

    session = tutorial_service.refresh_active_session()

    assert session.current_step == "candidate_published"
    assert session.publication_record_id is not None
    assert session.steps[-1].completed is False
    assert "without an Anki note id" in session.steps[-1].detail
