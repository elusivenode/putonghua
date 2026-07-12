import sqlite3

from putonghua.database.repositories import (
    ProjectRepository,
    PublicationRecordRepository,
    ReviewSuggestionCreateRecord,
    ReviewSuggestionRepository,
    SourceCreateRecord,
    SourceRepository,
    TranscriptSegmentRecord,
    TutorialSessionRepository,
)


def test_project_repository_creates_and_reuses_project() -> None:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute(
        """
        CREATE TABLE projects (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    repository = ProjectRepository(connection)

    first = repository.get_or_create_by_name("Mandarin Podcast")
    second = repository.get_or_create_by_name("Mandarin Podcast")

    assert first.name == "Mandarin Podcast"
    assert first.id == second.id


def test_source_repository_inserts_source_and_segments() -> None:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.executescript(
        """
        CREATE TABLE sources (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            source_type TEXT NOT NULL,
            title TEXT NOT NULL,
            content_hash TEXT NOT NULL,
            original_path TEXT,
            imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            external_id TEXT,
            channel_name TEXT,
            published_at TEXT,
            media_path TEXT,
            transcript_source TEXT,
            transcript_text TEXT,
            metadata_json TEXT NOT NULL DEFAULT '{}'
        );
        CREATE TABLE transcript_segments (
            id TEXT PRIMARY KEY,
            source_id TEXT NOT NULL,
            start_seconds REAL NOT NULL,
            end_seconds REAL NOT NULL,
            text TEXT NOT NULL,
            segment_index INTEGER NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """
    )

    repository = SourceRepository(connection)
    source_id = repository.create_source(
        SourceCreateRecord(
            project_id="project-1",
            source_type="youtube_audio",
            title="Episode 23",
            content_hash="abc123",
            original_path="https://youtube.com/watch?v=123",
            external_id="123",
            channel_name="Tea with Mona",
            published_at="20260710",
            media_path="/tmp/audio.webm",
            transcript_source="subtitles",
            transcript_text="first\nsecond",
            metadata={"id": "123"},
        ),
        [
            TranscriptSegmentRecord(0.0, 1.0, "first", 0),
            TranscriptSegmentRecord(1.0, 2.0, "second", 1),
        ],
    )

    source_row = connection.execute(
        "SELECT title, transcript_source FROM sources WHERE id = ?",
        (source_id,),
    ).fetchone()
    segment_count = connection.execute(
        "SELECT COUNT(*) FROM transcript_segments WHERE source_id = ?",
        (source_id,),
    ).fetchone()[0]

    assert source_row["title"] == "Episode 23"
    assert source_row["transcript_source"] == "subtitles"
    assert segment_count == 2


def test_review_suggestion_repository_replaces_and_lists() -> None:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.executescript(
        """
        CREATE TABLE review_conversations (
            id TEXT PRIMARY KEY,
            study_chunk_id TEXT NOT NULL,
            provider TEXT NOT NULL,
            model TEXT NOT NULL,
            prompt_version TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE review_messages (
            id TEXT PRIMARY KEY,
            conversation_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE study_chunks (
            id TEXT PRIMARY KEY,
            source_id TEXT NOT NULL,
            chunk_index INTEGER NOT NULL,
            start_seconds REAL NOT NULL,
            end_seconds REAL NOT NULL,
            text TEXT NOT NULL,
            transcript_segment_count INTEGER NOT NULL,
            char_count INTEGER NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            status TEXT NOT NULL DEFAULT 'pending',
            last_reviewed_at TEXT,
            notes TEXT
        );
        CREATE TABLE candidate_cards (
            id TEXT PRIMARY KEY
        );
        CREATE TABLE review_suggestions (
            id TEXT PRIMARY KEY,
            conversation_id TEXT NOT NULL,
            study_chunk_id TEXT NOT NULL,
            source_message_id TEXT,
            suggestion_index INTEGER NOT NULL,
            candidate_type TEXT NOT NULL,
            simplified TEXT NOT NULL,
            traditional TEXT NOT NULL,
            pinyin TEXT NOT NULL,
            english TEXT NOT NULL,
            rationale TEXT NOT NULL,
            source_excerpt TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'suggested',
            promoted_candidate_card_id TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (conversation_id, suggestion_index)
        );
        """
    )
    connection.execute(
        """
        INSERT INTO study_chunks(
            id, source_id, chunk_index, start_seconds, end_seconds, text,
            transcript_segment_count, char_count, status
        ) VALUES ('chunk-1', 'source-1', 0, 0.0, 10.0, '你好。', 1, 3, 'pending')
        """
    )
    connection.execute(
        """
        INSERT INTO review_conversations(
            id, study_chunk_id, provider, model, prompt_version
        )
        VALUES ('conv-1', 'chunk-1', 'openai', 'gpt-test', 'review/chunk_chat_v1.md')
        """
    )
    connection.execute(
        """
        INSERT INTO review_messages(id, conversation_id, role, content)
        VALUES ('msg-1', 'conv-1', 'assistant', 'reply')
        """
    )

    repository = ReviewSuggestionRepository(connection)
    first_ids = repository.replace_for_message(
        "msg-1",
        [
            ReviewSuggestionCreateRecord(
                conversation_id="conv-1",
                study_chunk_id="chunk-1",
                source_message_id="msg-1",
                suggestion_index=0,
                candidate_type="word",
                simplified="你好",
                traditional="你好",
                pinyin="ni3 hao3",
                english="hello",
                rationale="Useful greeting",
                source_excerpt="你好。",
            )
        ],
    )

    listed = repository.list_for_conversation("conv-1")

    assert len(first_ids) == 1
    assert len(listed) == 1
    assert listed[0].id == first_ids[0]
    assert listed[0].suggestion_index == 0
    assert listed[0].candidate_type == "word"
    assert listed[0].status == "suggested"

    second_ids = repository.replace_for_message(
        "msg-1",
        [
            ReviewSuggestionCreateRecord(
                conversation_id="conv-1",
                study_chunk_id="chunk-1",
                source_message_id="msg-1",
                suggestion_index=0,
                candidate_type="phrase",
                simplified="大家好",
                traditional="大家好",
                pinyin="da4 jia1 hao3",
                english="hello everyone",
                rationale="Updated suggestion",
                source_excerpt="大家好。",
            )
        ],
    )

    relisted = repository.list_for_conversation("conv-1")

    assert len(second_ids) == 1
    assert second_ids[0] != first_ids[0]
    assert len(relisted) == 1
    assert relisted[0].id == second_ids[0]
    assert relisted[0].candidate_type == "phrase"


def test_publication_record_repository_creates_and_marks_published() -> None:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.executescript(
        """
        CREATE TABLE publication_records (
            id TEXT PRIMARY KEY,
            candidate_card_id TEXT NOT NULL,
            putonghua_id TEXT NOT NULL UNIQUE,
            anki_note_id TEXT,
            published_at TEXT,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE UNIQUE INDEX idx_publication_records_candidate_card_id
        ON publication_records(candidate_card_id);
        """
    )

    repository = PublicationRecordRepository(connection)
    publication_id = repository.create_publication(
        candidate_id="candidate-1",
        putonghua_id="candidate-1",
        status="publishing",
    )
    repository.mark_published(publication_id, 42001)

    record = repository.get_by_candidate_id("candidate-1")

    assert record is not None
    assert record.id == publication_id
    assert record.putonghua_id == "candidate-1"
    assert record.anki_note_id == "42001"
    assert record.status == "published"


def test_tutorial_session_repository_tracks_active_and_reset_state() -> None:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.executescript(
        """
        CREATE TABLE tutorial_sessions (
            id TEXT PRIMARY KEY,
            status TEXT NOT NULL,
            current_step TEXT NOT NULL,
            project_id TEXT,
            source_id TEXT,
            study_chunk_id TEXT,
            review_conversation_id TEXT,
            review_suggestion_id TEXT,
            candidate_card_id TEXT,
            publication_record_id TEXT,
            completed_at TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE UNIQUE INDEX idx_tutorial_sessions_active
        ON tutorial_sessions(status)
        WHERE status = 'active';
        """
    )

    repository = TutorialSessionRepository(connection)
    session_id = repository.create_session(
        current_step="context_ready",
        project_id="project-1",
        source_id="source-1",
        study_chunk_id="chunk-1",
    )
    active = repository.get_active_session()

    assert active is not None
    assert active.id == session_id
    assert active.current_step == "context_ready"

    repository.update_session(
        session_id,
        status="completed",
        current_step="completed",
        project_id="project-1",
        source_id="source-1",
        study_chunk_id="chunk-1",
        review_conversation_id="conversation-1",
        review_suggestion_id="suggestion-1",
        candidate_card_id="candidate-1",
        publication_record_id="publication-1",
        completed_at=None,
    )
    completed = connection.execute(
        """
        SELECT status, current_step, review_conversation_id, completed_at
        FROM tutorial_sessions
        WHERE id = ?
        """,
        (session_id,),
    ).fetchone()

    assert completed["status"] == "completed"
    assert completed["current_step"] == "completed"
    assert completed["review_conversation_id"] == "conversation-1"
    assert completed["completed_at"] is not None

    second_session_id = repository.create_session(
        current_step="context_ready",
        project_id=None,
        source_id=None,
        study_chunk_id=None,
    )
    repository.mark_reset(second_session_id)

    assert repository.get_active_session() is None
