from __future__ import annotations

from dataclasses import replace
from io import StringIO
from pathlib import Path
from typing import cast

from rich.console import Console

from putonghua.cli.tui import run_tui_session
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
from putonghua.models.anki import AnkiPublishNoteRequest, AnkiPublishNoteResult
from putonghua.models.candidates import CandidateDraft
from putonghua.models.tutorial import TutorialSessionView, TutorialStepView
from putonghua.services.candidate_publish import (
    CandidatePublishConfig,
    CandidatePublishService,
)
from putonghua.services.chunk_review import ChunkReviewService
from putonghua.services.review_suggestions import ReviewSuggestionService
from putonghua.services.tui_session import TuiSessionService
from putonghua.services.tutorial import TutorialService
from putonghua.tests_support import FakeReviewProvider


class _FakeAnkiPublishProvider:
    def __init__(self) -> None:
        self.requests: list[AnkiPublishNoteRequest] = []

    def publish_note(self, request: AnkiPublishNoteRequest) -> AnkiPublishNoteResult:
        self.requests.append(request)
        return AnkiPublishNoteResult(note_id=42001)


def test_tui_session_service_builds_dashboard(tmp_path: Path) -> None:
    database_path = tmp_path / "putonghua.db"
    migrate_database(database_path)

    with connect(database_path) as connection:
        projects = ProjectRepository(connection)
        sources = SourceRepository(connection)
        chunks = StudyChunkRepository(connection)
        candidates = CandidateRepository(connection)

        project_one = projects.get_or_create_by_name("Mandarin Podcast")
        project_two = projects.get_or_create_by_name("Story Club")

        first_source_id = sources.create_source(
            SourceCreateRecord(
                project_id=project_one.id,
                source_type="youtube_audio",
                title="Episode 23",
                content_hash="source-1",
                original_path="https://youtube.com/watch?v=abc123",
                external_id="abc123",
                channel_name="Tea with Mona",
                published_at="20260712",
                media_path="/tmp/episode.webm",
                transcript_source="subtitles",
                transcript_text="你好 我们开始吧",
                metadata={"id": "abc123"},
            ),
            [
                TranscriptSegmentRecord(0.0, 10.0, "你好", 0),
                TranscriptSegmentRecord(10.0, 20.0, "我们开始吧", 1),
            ],
        )
        sources.create_source(
            SourceCreateRecord(
                project_id=project_two.id,
                source_type="youtube_audio",
                title="Episode 1",
                content_hash="source-2",
                original_path="https://youtube.com/watch?v=def456",
                external_id="def456",
                channel_name="Story Club",
                published_at="20260712",
                media_path="/tmp/story.webm",
                transcript_source="openai_transcription",
                transcript_text="大家好",
                metadata={"id": "def456"},
            ),
            [TranscriptSegmentRecord(0.0, 5.0, "大家好", 0)],
        )

        chunk_ids = chunks.replace_for_source(
            first_source_id,
            [
                StudyChunkRecord(
                    source_id=first_source_id,
                    chunk_index=0,
                    start_seconds=0.0,
                    end_seconds=15.0,
                    text="你好",
                    transcript_segment_count=1,
                    char_count=2,
                    status="completed",
                ),
                StudyChunkRecord(
                    source_id=first_source_id,
                    chunk_index=1,
                    start_seconds=15.0,
                    end_seconds=30.0,
                    text="我们开始吧",
                    transcript_segment_count=1,
                    char_count=5,
                    status="pending",
                ),
            ],
        )
        candidates.create_candidates(
            [
                CandidateCardCreateRecord(
                    project_id=project_one.id,
                    source_id=first_source_id,
                    study_chunk_id=chunk_ids[0],
                    candidate_type="word",
                    simplified="你好",
                    traditional="你好",
                    pinyin="ni3 hao3",
                    english="hello",
                    provenance={"source": "test"},
                )
            ]
        )

    service = TuiSessionService(database_path=database_path)
    dashboard = service.get_dashboard()

    assert [project.name for project in dashboard.projects] == [
        "Mandarin Podcast",
        "Story Club",
    ]
    assert dashboard.selected_project_id == dashboard.projects[0].id
    assert dashboard.selected_source_id == dashboard.sources[0].id
    assert len(dashboard.chunks) == 2
    assert dashboard.chunks[0].candidate_count == 1
    assert dashboard.sources[0].pending_chunk_count == 1
    assert dashboard.review_context is None


def test_tui_session_service_includes_tutorial_panel_when_active(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "putonghua.db"
    service = TuiSessionService(
        database_path=database_path,
        tutorial_service=TutorialService(database_path),
    )

    session = service.start_tutorial()
    dashboard = service.get_dashboard()

    assert dashboard.tutorial is not None
    assert dashboard.tutorial.current_step == "session_layout"
    assert dashboard.tutorial.project_id == session.project_id
    assert dashboard.tutorial.source_id == session.source_id
    assert dashboard.selected_project_id == session.project_id
    assert dashboard.selected_source_id == session.source_id
    assert len(dashboard.chunks) == 2
    assert dashboard.chunks[0].status == "completed"


def test_tui_session_service_falls_back_when_selection_is_missing(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "putonghua.db"
    migrate_database(database_path)

    with connect(database_path) as connection:
        project = ProjectRepository(connection).get_or_create_by_name(
            "Mandarin Podcast"
        )
        source_id = SourceRepository(connection).create_source(
            SourceCreateRecord(
                project_id=project.id,
                source_type="youtube_audio",
                title="Episode 23",
                content_hash="source-1",
                original_path="https://youtube.com/watch?v=abc123",
                external_id="abc123",
                channel_name="Tea with Mona",
                published_at="20260712",
                media_path="/tmp/episode.webm",
                transcript_source="subtitles",
                transcript_text="你好",
                metadata={"id": "abc123"},
            ),
            [TranscriptSegmentRecord(0.0, 5.0, "你好", 0)],
        )
        StudyChunkRepository(connection).replace_for_source(
            source_id,
            [
                StudyChunkRecord(
                    source_id=source_id,
                    chunk_index=0,
                    start_seconds=0.0,
                    end_seconds=5.0,
                    text="你好",
                    transcript_segment_count=1,
                    char_count=2,
                )
            ],
        )

    dashboard = TuiSessionService(database_path=database_path).get_dashboard(
        selected_project_id="missing-project",
        selected_source_id="missing-source",
        selected_chunk_id="missing-chunk",
    )

    assert dashboard.selected_project_id == dashboard.projects[0].id
    assert dashboard.selected_source_id == dashboard.sources[0].id
    assert dashboard.selected_chunk_id == dashboard.chunks[0].id
    assert dashboard.review_context is None


def test_tui_session_service_includes_latest_review_context(tmp_path: Path) -> None:
    database_path = tmp_path / "putonghua.db"
    migrate_database(database_path)

    with connect(database_path) as connection:
        projects = ProjectRepository(connection)
        sources = SourceRepository(connection)
        chunks = StudyChunkRepository(connection)

        project = projects.get_or_create_by_name("Mandarin Podcast")
        source_id = sources.create_source(
            SourceCreateRecord(
                project_id=project.id,
                source_type="youtube_audio",
                title="Episode 23",
                content_hash="source-1",
                original_path="https://youtube.com/watch?v=abc123",
                external_id="abc123",
                channel_name="Tea with Mona",
                published_at="20260712",
                media_path="/tmp/episode.webm",
                transcript_source="subtitles",
                transcript_text="我会尽量地把每一个字都说出来。",
                metadata={"id": "abc123"},
            ),
            [TranscriptSegmentRecord(0.0, 30.0, "我会尽量地把每一个字都说出来。", 0)],
        )
        chunk_id = chunks.replace_for_source(
            source_id,
            [
                StudyChunkRecord(
                    source_id=source_id,
                    chunk_index=0,
                    start_seconds=0.0,
                    end_seconds=30.0,
                    text="我会尽量地把每一个字都说出来。",
                    transcript_segment_count=1,
                    char_count=15,
                    status="pending",
                )
            ],
        )[0]

    review_service = ChunkReviewService(
        database_path=database_path,
        provider=FakeReviewProvider(),
        provider_name="fake-openai",
        model_name="test-model",
    )
    result = review_service.chat_for_chunk(chunk_id, "Prefer sentence cards.")

    dashboard = TuiSessionService(database_path=database_path).get_dashboard(
        selected_chunk_id=chunk_id,
    )

    assert dashboard.review_context is not None
    assert dashboard.review_context.conversation_id == result.conversation_id
    assert dashboard.review_context.messages[-1].role == "assistant"
    assert any(
        candidate.candidate_type == "sentence" for candidate in dashboard.candidates
    )


def test_tui_session_service_promotes_review_suggestion(tmp_path: Path) -> None:
    database_path = tmp_path / "putonghua.db"
    migrate_database(database_path)

    with connect(database_path) as connection:
        projects = ProjectRepository(connection)
        sources = SourceRepository(connection)
        chunks = StudyChunkRepository(connection)

        project = projects.get_or_create_by_name("Mandarin Podcast")
        source_id = sources.create_source(
            SourceCreateRecord(
                project_id=project.id,
                source_type="youtube_audio",
                title="Episode 23",
                content_hash="source-1",
                original_path="https://youtube.com/watch?v=abc123",
                external_id="abc123",
                channel_name="Tea with Mona",
                published_at="20260712",
                media_path="/tmp/episode.webm",
                transcript_source="subtitles",
                transcript_text="我会尽量地把每一个字都说出来。",
                metadata={"id": "abc123"},
            ),
            [TranscriptSegmentRecord(0.0, 30.0, "我会尽量地把每一个字都说出来。", 0)],
        )
        chunk_id = chunks.replace_for_source(
            source_id,
            [
                StudyChunkRecord(
                    source_id=source_id,
                    chunk_index=0,
                    start_seconds=0.0,
                    end_seconds=30.0,
                    text="我会尽量地把每一个字都说出来。",
                    transcript_segment_count=1,
                    char_count=15,
                    status="pending",
                )
            ],
        )[0]

    review_service = ChunkReviewService(
        database_path=database_path,
        provider=FakeReviewProvider(),
        provider_name="fake-openai",
        model_name="test-model",
    )
    chat_result = review_service.chat_for_chunk(chunk_id, "Prefer sentence cards.")
    suggestion_id = (
        ReviewSuggestionService(database_path)
        .list_review_suggestions(chat_result.conversation_id)[0]
        .id
    )

    service = TuiSessionService(database_path=database_path)
    result = service.promote_suggestion(suggestion_id)
    dashboard = service.get_dashboard(selected_chunk_id=chunk_id)

    assert result.suggestion_id == suggestion_id
    assert result.status == "promoted"
    assert dashboard.review_context is not None
    assert any(candidate.status == "promoted" for candidate in dashboard.candidates)


def test_tui_session_service_publishes_chunk_candidate(tmp_path: Path) -> None:
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
    publish_service = CandidatePublishService(
        database_path=database_path,
        provider=provider,
        config=CandidatePublishConfig(
            deck_name="Mandarin",
            note_type_name="Mandarin vocab",
            publish_tags=["putonghua-test"],
        ),
    )
    from putonghua.models.tui import TuiPublishTargetView

    service = TuiSessionService(
        database_path=database_path,
        publish_service=publish_service,
        publish_target=TuiPublishTargetView(
            deck_name="Mandarin",
            note_type_name="Mandarin vocab",
            publish_tags=["putonghua-test"],
        ),
    )

    result = service.publish_candidate(candidate_id)
    dashboard = service.get_dashboard(selected_chunk_id="chunk-1")

    assert result.candidate_id == candidate_id
    assert result.anki_note_id == 42001
    assert result.created is True
    assert provider.requests[0].deck_name == "Mandarin"
    assert dashboard.candidates[0].status == "published"
    assert dashboard.candidates[0].publication_status == "published"
    assert dashboard.candidates[0].anki_note_id == 42001
    with connect(database_path) as connection:
        publication = PublicationRecordRepository(connection).get_by_candidate_id(
            candidate_id
        )
    assert publication is not None
    assert publication.status == "published"


def test_tui_session_service_promotes_extracted_candidate_without_chat(
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
                original_path="https://youtube.com/watch?v=promote001",
                external_id="promote001",
                channel_name="Tea with Mona",
                published_at="20260712",
                media_path="/tmp/episode.webm",
                transcript_source="subtitles",
                transcript_text="开始",
                metadata={"id": "promote001"},
            ),
            [TranscriptSegmentRecord(0.0, 2.0, "开始", 0)],
        )
        chunk_id = StudyChunkRepository(connection).replace_for_source(
            source_id,
            [
                StudyChunkRecord(
                    source_id=source_id,
                    chunk_index=0,
                    start_seconds=0.0,
                    end_seconds=2.0,
                    text="开始",
                    transcript_segment_count=1,
                    char_count=2,
                    status="pending",
                )
            ],
        )[0]
        candidate_id = CandidateRepository(connection).create_candidates(
            [
                CandidateCardCreateRecord(
                    project_id=project.id,
                    source_id=source_id,
                    study_chunk_id=chunk_id,
                    candidate_type="word",
                    simplified="开始",
                    traditional="開始",
                    pinyin="kai1 shi3",
                    english="to begin",
                    provenance={"origin": "test"},
                )
            ]
        )[0]
        connection.commit()

    service = TuiSessionService(database_path=database_path)
    result = service.promote_candidate(candidate_id)
    dashboard = service.get_dashboard(selected_chunk_id=chunk_id)

    assert result.candidate_id == candidate_id
    assert result.status == "promoted"
    assert result.created is True
    assert dashboard.candidates[0].status == "promoted"


def test_tui_session_service_completes_chunk(tmp_path: Path) -> None:
    database_path = tmp_path / "putonghua.db"
    migrate_database(database_path)

    with connect(database_path) as connection:
        project = ProjectRepository(connection).get_or_create_by_name("Podcast Project")
        source_id = SourceRepository(connection).create_source(
            SourceCreateRecord(
                project_id=project.id,
                source_type="youtube_audio",
                title="Episode 29",
                content_hash="hash-7",
                original_path="https://youtube.com/watch?v=complete001",
                external_id="complete001",
                channel_name="Tea with Mona",
                published_at="20260712",
                media_path="/tmp/episode.webm",
                transcript_source="subtitles",
                transcript_text="你好 我们开始吧",
                metadata={"id": "complete001"},
            ),
            [
                TranscriptSegmentRecord(0.0, 5.0, "你好", 0),
                TranscriptSegmentRecord(5.0, 10.0, "我们开始吧", 1),
            ],
        )
        chunk_id = StudyChunkRepository(connection).replace_for_source(
            source_id,
            [
                StudyChunkRecord(
                    source_id=source_id,
                    chunk_index=0,
                    start_seconds=0.0,
                    end_seconds=5.0,
                    text="你好",
                    transcript_segment_count=1,
                    char_count=2,
                    status="pending",
                ),
                StudyChunkRecord(
                    source_id=source_id,
                    chunk_index=1,
                    start_seconds=5.0,
                    end_seconds=10.0,
                    text="我们开始吧",
                    transcript_segment_count=1,
                    char_count=5,
                    status="pending",
                ),
            ],
        )[0]
        connection.commit()

    service = TuiSessionService(database_path=database_path)
    service.complete_chunk(chunk_id)
    dashboard = service.get_dashboard(selected_source_id=source_id)

    completed = next(chunk for chunk in dashboard.chunks if chunk.id == chunk_id)
    assert completed.status == "completed"


def test_run_tui_session_supports_help_navigation_and_quit() -> None:
    class _FakeService:
        def get_dashboard(
            self,
            *,
            selected_project_id: str | None = None,
            selected_source_id: str | None = None,
            selected_chunk_id: str | None = None,
        ):
            from putonghua.models.tui import (
                TuiChunkView,
                TuiDashboardView,
                TuiProjectView,
                TuiSourceView,
            )

            return TuiDashboardView(
                selected_project_id=selected_project_id or "project-1",
                selected_source_id=selected_source_id or "source-1",
                selected_chunk_id=selected_chunk_id or "chunk-1",
                projects=[TuiProjectView("project-1", "Mandarin Podcast", 1)],
                sources=[
                    TuiSourceView(
                        "source-1",
                        "project-1",
                        "Episode 23",
                        "youtube_audio",
                        "subtitles",
                        2,
                        2,
                        1,
                    )
                ],
                chunks=[
                    TuiChunkView(
                        "chunk-1",
                        "source-1",
                        0,
                        "completed",
                        10,
                        1,
                        0.0,
                        12.0,
                        "你好",
                    ),
                    TuiChunkView(
                        "chunk-2",
                        "source-1",
                        1,
                        "pending",
                        18,
                        0,
                        12.0,
                        30.0,
                        "我们开始吧",
                    ),
                ],
                candidates=[],
                review_context=None,
                publish_target=None,
            )

    commands = iter(["help", "c 2", "n", "quit"])
    output = StringIO()
    console = Console(file=output, force_terminal=False, color_system=None)

    run_tui_session(
        service=cast(TuiSessionService, _FakeService()),
        console=console,
        input_func=lambda _: next(commands),
    )

    rendered = output.getvalue()
    assert "Putonghua TUI session" in rendered
    assert "Selected chunk 2." in rendered
    assert "Leaving putonghua TUI." in rendered


def test_run_tui_session_supports_complete_and_advances() -> None:
    class _FakeService:
        completed = False

        def get_dashboard(
            self,
            *,
            selected_project_id: str | None = None,
            selected_source_id: str | None = None,
            selected_chunk_id: str | None = None,
        ):
            from putonghua.models.tui import (
                TuiChunkView,
                TuiDashboardView,
                TuiProjectView,
                TuiSourceView,
            )

            first_status = "completed" if self.completed else "pending"
            selected = selected_chunk_id or "chunk-1"
            return TuiDashboardView(
                selected_project_id=selected_project_id or "project-1",
                selected_source_id=selected_source_id or "source-1",
                selected_chunk_id=selected,
                projects=[TuiProjectView("project-1", "Mandarin Podcast", 1)],
                sources=[
                    TuiSourceView(
                        "source-1",
                        "project-1",
                        "Episode 23",
                        "youtube_audio",
                        "subtitles",
                        0,
                        2,
                        1,
                    )
                ],
                chunks=[
                    TuiChunkView(
                        "chunk-1",
                        "source-1",
                        0,
                        first_status,
                        10,
                        0,
                        0.0,
                        12.0,
                        "你好",
                    ),
                    TuiChunkView(
                        "chunk-2",
                        "source-1",
                        1,
                        "pending",
                        18,
                        0,
                        12.0,
                        30.0,
                        "我们开始吧",
                    ),
                ],
                candidates=[],
                review_context=None,
                publish_target=None,
            )

        def complete_chunk(self, chunk_id: str) -> None:
            assert chunk_id == "chunk-1"
            self.completed = True

    commands = iter(["done", "quit"])
    output = StringIO()
    console = Console(file=output, force_terminal=False, color_system=None)

    run_tui_session(
        service=cast(TuiSessionService, _FakeService()),
        console=console,
        input_func=lambda _: next(commands),
    )

    rendered = output.getvalue()
    assert "Marked chunk 1 completed. Selected chunk 2." in rendered


def test_run_tui_session_supports_complete_without_next_chunk() -> None:
    class _FakeService:
        completed = False

        def get_dashboard(
            self,
            *,
            selected_project_id: str | None = None,
            selected_source_id: str | None = None,
            selected_chunk_id: str | None = None,
        ):
            from putonghua.models.tui import (
                TuiChunkView,
                TuiDashboardView,
                TuiProjectView,
                TuiSourceView,
            )

            status = "completed" if self.completed else "pending"
            return TuiDashboardView(
                selected_project_id=selected_project_id or "project-1",
                selected_source_id=selected_source_id or "source-1",
                selected_chunk_id=selected_chunk_id or "chunk-1",
                projects=[TuiProjectView("project-1", "Mandarin Podcast", 1)],
                sources=[
                    TuiSourceView(
                        "source-1",
                        "project-1",
                        "Episode 23",
                        "youtube_audio",
                        "subtitles",
                        0,
                        1,
                        0,
                    )
                ],
                chunks=[
                    TuiChunkView(
                        "chunk-1",
                        "source-1",
                        0,
                        status,
                        10,
                        0,
                        0.0,
                        12.0,
                        "你好",
                    )
                ],
                candidates=[],
                review_context=None,
                publish_target=None,
            )

        def complete_chunk(self, chunk_id: str) -> None:
            assert chunk_id == "chunk-1"
            self.completed = True

    commands = iter(["complete", "quit"])
    output = StringIO()
    console = Console(file=output, force_terminal=False, color_system=None)

    run_tui_session(
        service=cast(TuiSessionService, _FakeService()),
        console=console,
        input_func=lambda _: next(commands),
    )

    rendered = output.getvalue()
    assert "Marked chunk 1 completed." in rendered
    assert "No other pending chunk" in rendered


def test_run_tui_session_supports_extract_and_chat() -> None:
    class _ExtractionResult:
        chunk_id = "chunk-2"
        candidate_count = 2
        candidate_ids = ["candidate-1", "candidate-2"]

    class _ChatResult:
        conversation_id = "conversation-1"
        assistant_text = "Prioritize the full sentence."
        suggested_cards = [
            CandidateDraft(
                candidate_type="sentence",
                simplified="我们开始吧。",
                traditional="我們開始吧。",
                pinyin="wǒ men kāi shǐ ba",
                english="Let's begin.",
                rationale="Useful full sentence card.",
                source_excerpt="我们开始吧",
            )
        ]

    class _FakeService:
        def get_dashboard(
            self,
            *,
            selected_project_id: str | None = None,
            selected_source_id: str | None = None,
            selected_chunk_id: str | None = None,
        ):
            from putonghua.models.tui import (
                TuiCandidateView,
                TuiChunkView,
                TuiDashboardView,
                TuiProjectView,
                TuiReviewContextView,
                TuiReviewMessageView,
                TuiSourceView,
            )

            review_context = None
            if selected_chunk_id == "chunk-2":
                review_context = TuiReviewContextView(
                    conversation_id="conversation-1",
                    messages=[
                        TuiReviewMessageView(
                            "assistant",
                            "Prioritize the full sentence.",
                        )
                    ],
                )

            return TuiDashboardView(
                selected_project_id=selected_project_id or "project-1",
                selected_source_id=selected_source_id or "source-1",
                selected_chunk_id=selected_chunk_id or "chunk-2",
                projects=[TuiProjectView("project-1", "Mandarin Podcast", 1)],
                sources=[
                    TuiSourceView(
                        "source-1",
                        "project-1",
                        "Episode 23",
                        "youtube_audio",
                        "subtitles",
                        2,
                        2,
                        1,
                    )
                ],
                chunks=[
                    TuiChunkView(
                        "chunk-2",
                        "source-1",
                        1,
                        "pending",
                        18,
                        0,
                        12.0,
                        30.0,
                        "我们开始吧",
                    )
                ],
                candidates=[
                    TuiCandidateView(
                        id="candidate-1",
                        candidate_type="sentence",
                        simplified="我们开始吧。",
                        english="Let's begin.",
                        status="proposed",
                        publication_status=None,
                        anki_note_id=None,
                    )
                ],
                review_context=review_context,
                publish_target=None,
            )

        def extract_chunk(self, chunk_id: str) -> _ExtractionResult:
            assert chunk_id == "chunk-2"
            return _ExtractionResult()

        def chat_for_chunk(self, chunk_id: str, prompt: str) -> _ChatResult:
            assert chunk_id == "chunk-2"
            assert prompt == "Suggest a sentence card."
            return _ChatResult()

    commands = iter(["extract", "chat Suggest a sentence card.", "quit"])
    output = StringIO()
    console = Console(file=output, force_terminal=False, color_system=None)

    run_tui_session(
        service=cast(TuiSessionService, _FakeService()),
        console=console,
        input_func=lambda _: next(commands),
    )

    rendered = output.getvalue()
    assert "Extracted 2 candidate cards for chunk chunk-2" in rendered
    assert "Conversation ID: conversation-1" in rendered
    assert "Added candidates: 1" in rendered


def test_run_tui_session_supports_promote() -> None:
    class _PromotionResult:
        suggestion_id = ""
        candidate_id = "candidate-9"
        status = "promoted"
        created = True

    class _FakeService:
        promoted = False

        def get_dashboard(
            self,
            *,
            selected_project_id: str | None = None,
            selected_source_id: str | None = None,
            selected_chunk_id: str | None = None,
        ):
            from putonghua.models.tui import (
                TuiCandidateView,
                TuiChunkView,
                TuiDashboardView,
                TuiProjectView,
                TuiReviewContextView,
                TuiReviewMessageView,
                TuiSourceView,
            )

            return TuiDashboardView(
                selected_project_id=selected_project_id or "project-1",
                selected_source_id=selected_source_id or "source-1",
                selected_chunk_id=selected_chunk_id or "chunk-2",
                projects=[TuiProjectView("project-1", "Mandarin Podcast", 1)],
                sources=[
                    TuiSourceView(
                        "source-1",
                        "project-1",
                        "Episode 23",
                        "youtube_audio",
                        "subtitles",
                        2,
                        2,
                        1,
                    )
                ],
                chunks=[
                    TuiChunkView(
                        "chunk-2",
                        "source-1",
                        1,
                        "pending",
                        18,
                        0,
                        12.0,
                        30.0,
                        "我们开始吧",
                    )
                ],
                candidates=[
                    TuiCandidateView(
                        id="candidate-9",
                        candidate_type="sentence",
                        simplified="我们开始吧。",
                        english="Let's begin.",
                        status="promoted" if self.promoted else "proposed",
                        publication_status=None,
                        anki_note_id=None,
                    )
                ],
                review_context=TuiReviewContextView(
                    conversation_id="conversation-1",
                    messages=[
                        TuiReviewMessageView(
                            "assistant",
                            "Prioritize the full sentence.",
                        )
                    ],
                ),
                publish_target=None,
            )

        def promote_candidate(self, candidate_id: str) -> _PromotionResult:
            assert candidate_id == "candidate-9"
            self.promoted = True
            return _PromotionResult()

    commands = iter(["promote", "quit"])
    output = StringIO()
    console = Console(file=output, force_terminal=False, color_system=None)

    run_tui_session(
        service=cast(TuiSessionService, _FakeService()),
        console=console,
        input_func=lambda _: next(commands),
    )

    rendered = output.getvalue()
    assert "Candidate ID: candidate-9" in rendered
    assert "Candidate added to the publish queue" in rendered
    assert "sentence | 我们开始吧。 | Let's begin. | ready to publish" in rendered


def test_run_tui_session_supports_promote_without_review_suggestions() -> None:
    class _PromotionResult:
        suggestion_id = ""
        candidate_id = "candidate-3"
        status = "promoted"
        created = True

    class _FakeService:
        promoted = False

        def get_dashboard(
            self,
            *,
            selected_project_id: str | None = None,
            selected_source_id: str | None = None,
            selected_chunk_id: str | None = None,
        ):
            from putonghua.models.tui import (
                TuiCandidateView,
                TuiChunkView,
                TuiDashboardView,
                TuiProjectView,
                TuiSourceView,
            )

            return TuiDashboardView(
                selected_project_id=selected_project_id or "project-1",
                selected_source_id=selected_source_id or "source-1",
                selected_chunk_id=selected_chunk_id or "chunk-2",
                projects=[TuiProjectView("project-1", "Mandarin Podcast", 1)],
                sources=[
                    TuiSourceView(
                        "source-1",
                        "project-1",
                        "Episode 23",
                        "youtube_audio",
                        "subtitles",
                        1,
                        1,
                        1,
                    )
                ],
                chunks=[
                    TuiChunkView(
                        "chunk-2",
                        "source-1",
                        1,
                        "pending",
                        18,
                        1,
                        12.0,
                        30.0,
                        "我们开始吧",
                    )
                ],
                candidates=[
                    TuiCandidateView(
                        id="candidate-3",
                        candidate_type="phrase",
                        simplified="开始",
                        english="to begin",
                        status="promoted" if self.promoted else "proposed",
                        publication_status=None,
                        anki_note_id=None,
                    )
                ],
                review_context=None,
                publish_target=None,
            )

        def promote_candidate(self, candidate_id: str) -> _PromotionResult:
            assert candidate_id == "candidate-3"
            self.promoted = True
            return _PromotionResult()

    commands = iter(["promote", "quit"])
    output = StringIO()
    console = Console(file=output, force_terminal=False, color_system=None)

    run_tui_session(
        service=cast(TuiSessionService, _FakeService()),
        console=console,
        input_func=lambda _: next(commands),
    )

    rendered = output.getvalue()
    assert "Candidate ID: candidate-3" in rendered
    assert "Candidate added to the publish queue" in rendered
    assert "phrase | 开始 | to begin | ready to publish" in rendered


def test_run_tui_session_renders_wrapped_review_text_and_all_candidates() -> None:
    class _FakeService:
        def get_dashboard(
            self,
            *,
            selected_project_id: str | None = None,
            selected_source_id: str | None = None,
            selected_chunk_id: str | None = None,
        ):
            from putonghua.models.tui import (
                TuiCandidateView,
                TuiChunkView,
                TuiDashboardView,
                TuiProjectView,
                TuiReviewContextView,
                TuiReviewMessageView,
                TuiSourceView,
            )

            return TuiDashboardView(
                selected_project_id=selected_project_id or "project-1",
                selected_source_id=selected_source_id or "source-1",
                selected_chunk_id=selected_chunk_id or "chunk-1",
                projects=[TuiProjectView("project-1", "Mandarin Podcast", 1)],
                sources=[
                    TuiSourceView(
                        "source-1",
                        "project-1",
                        "Episode 23",
                        "youtube_audio",
                        "subtitles",
                        7,
                        1,
                        1,
                    )
                ],
                chunks=[
                    TuiChunkView(
                        "chunk-1",
                        "source-1",
                        0,
                        "pending",
                        105,
                        7,
                        0.0,
                        46.0,
                        (
                            "大家好，欢迎大家来到 Chinese Podcast with 盛兰。"
                            "在每一期的节目中，我都会用中文和大家聊一些有趣的话题。"
                        ),
                    )
                ],
                candidates=[
                    TuiCandidateView(
                        id=f"candidate-{index}",
                        candidate_type="word",
                        simplified=f"候选{index}",
                        english=f"candidate {index}",
                        status="proposed",
                        publication_status=None,
                        anki_note_id=None,
                    )
                    for index in range(1, 8)
                ],
                review_context=TuiReviewContextView(
                    conversation_id="conversation-1",
                    messages=[
                        TuiReviewMessageView(
                            "assistant",
                            (
                                "This is a deliberately long assistant response that "
                                "should wrap across multiple lines instead of "
                                "running off the screen in one unreadable row."
                            ),
                        )
                    ],
                ),
                publish_target=None,
                tutorial=None,
            )

    commands = iter(["quit"])
    output = StringIO()
    console = Console(file=output, force_terminal=False, color_system=None)

    run_tui_session(
        service=cast(TuiSessionService, _FakeService()),
        console=console,
        input_func=lambda _: next(commands),
    )

    rendered = output.getvalue()
    assert "Latest assistant:" in rendered
    assert "running off the screen in one unreadable row." in rendered
    assert "Chunk Candidates: 7" in rendered
    assert "7. word | 候选7 | candidate 7 | proposed" in rendered


def test_run_tui_session_supports_publish() -> None:
    class _PublishResult:
        candidate_id = "candidate-9"
        publication_record_id = "publication-4"
        anki_note_id = 42001
        status = "published"
        created = True

    class _FakeService:
        published = False

        def get_dashboard(
            self,
            *,
            selected_project_id: str | None = None,
            selected_source_id: str | None = None,
            selected_chunk_id: str | None = None,
        ):
            from putonghua.models.tui import (
                TuiCandidateView,
                TuiChunkView,
                TuiDashboardView,
                TuiProjectView,
                TuiPublishTargetView,
                TuiSourceView,
            )

            note_id = 42001 if self.published else None
            status = "published" if self.published else "promoted"

            return TuiDashboardView(
                selected_project_id=selected_project_id or "project-1",
                selected_source_id=selected_source_id or "source-1",
                selected_chunk_id=selected_chunk_id or "chunk-2",
                projects=[TuiProjectView("project-1", "Mandarin Podcast", 1)],
                sources=[
                    TuiSourceView(
                        "source-1",
                        "project-1",
                        "Episode 23",
                        "youtube_audio",
                        "subtitles",
                        2,
                        2,
                        1,
                    )
                ],
                chunks=[
                    TuiChunkView(
                        "chunk-2",
                        "source-1",
                        1,
                        "completed",
                        18,
                        1,
                        12.0,
                        30.0,
                        "我们开始吧",
                    )
                ],
                candidates=[
                    TuiCandidateView(
                        id="candidate-9",
                        candidate_type="sentence",
                        simplified="我们开始吧。",
                        english="Let's begin.",
                        status=status,
                        publication_status="published" if self.published else None,
                        anki_note_id=note_id,
                    )
                ],
                review_context=None,
                publish_target=TuiPublishTargetView(
                    deck_name="Mandarin",
                    note_type_name="Mandarin vocab",
                    publish_tags=["putonghua-test"],
                ),
            )

        def publish_candidate(self, candidate_id: str) -> _PublishResult:
            assert candidate_id == "candidate-9"
            self.published = True
            return _PublishResult()

    commands = iter(["publish", "y", "quit"])
    output = StringIO()
    console = Console(file=output, force_terminal=False, color_system=None)

    run_tui_session(
        service=cast(TuiSessionService, _FakeService()),
        console=console,
        input_func=lambda _: next(commands),
    )

    rendered = output.getvalue()
    assert "Deck: Mandarin" in rendered
    assert "Note Type: Mandarin vocab" in rendered
    assert "Anki Note ID: 42001" in rendered
    assert "Created new Anki note" in rendered
    assert "Publish Queue: 0 ready, 1 published locally" in rendered
    assert (
        "sentence | 我们开始吧。 | Let's begin. | published locally | note 42001"
        in rendered
    )


def test_run_tui_session_surfaces_local_publish_duplicate() -> None:
    class _PublishResult:
        candidate_id = "candidate-9"
        publication_record_id = "publication-4"
        anki_note_id = 42001
        status = "published"
        created = False

    class _FakeService:
        def get_dashboard(
            self,
            *,
            selected_project_id: str | None = None,
            selected_source_id: str | None = None,
            selected_chunk_id: str | None = None,
        ):
            from putonghua.models.tui import (
                TuiCandidateView,
                TuiChunkView,
                TuiDashboardView,
                TuiProjectView,
                TuiPublishTargetView,
                TuiSourceView,
            )

            return TuiDashboardView(
                selected_project_id=selected_project_id or "project-1",
                selected_source_id=selected_source_id or "source-1",
                selected_chunk_id=selected_chunk_id or "chunk-2",
                projects=[TuiProjectView("project-1", "Mandarin Podcast", 1)],
                sources=[
                    TuiSourceView(
                        "source-1",
                        "project-1",
                        "Episode 23",
                        "youtube_audio",
                        "subtitles",
                        2,
                        2,
                        1,
                    )
                ],
                chunks=[
                    TuiChunkView(
                        "chunk-2",
                        "source-1",
                        1,
                        "completed",
                        18,
                        1,
                        12.0,
                        30.0,
                        "我们开始吧",
                    )
                ],
                candidates=[
                    TuiCandidateView(
                        id="candidate-9",
                        candidate_type="sentence",
                        simplified="我们开始吧。",
                        english="Let's begin.",
                        status="published",
                        publication_status="published",
                        anki_note_id=42001,
                    )
                ],
                review_context=None,
                publish_target=TuiPublishTargetView(
                    deck_name="Mandarin",
                    note_type_name="Mandarin vocab",
                    publish_tags=["putonghua-test"],
                ),
            )

        def publish_candidate(self, candidate_id: str) -> _PublishResult:
            assert candidate_id == "candidate-9"
            return _PublishResult()

    commands = iter(["publish", "y", "quit"])
    output = StringIO()
    console = Console(file=output, force_terminal=False, color_system=None)

    run_tui_session(
        service=cast(TuiSessionService, _FakeService()),
        console=console,
        input_func=lambda _: next(commands),
    )

    rendered = output.getvalue()
    assert "Candidate already published locally as note 42001." in rendered
    assert "Anki note already existed locally" in rendered
    assert "Skipped remote publish and reused the local publication record" in rendered


def test_run_tui_session_supports_tutorial_entry_status_and_reset() -> None:
    class _FakeService:
        def __init__(self) -> None:
            self.active = False
            self.session = TutorialSessionView(
                id="tutorial-session-1",
                status="active",
                current_step="session_layout",
                project_id="project-1",
                source_id="source-1",
                study_chunk_id=None,
                review_conversation_id=None,
                review_suggestion_id=None,
                candidate_card_id=None,
                publication_record_id=None,
                completed_at=None,
                steps=[
                    TutorialStepView(
                        key="session_layout",
                        title="Understand the session layout",
                        command="tutorial next",
                        actions=[
                            "Look at the four main areas: Projects, Sources, "
                            "Chunks, and Focus.",
                            "Projects contain sources. Sources contain chunks. "
                            "Focus shows the selected chunk details.",
                            "When that mental model makes sense, type `tutorial next`.",
                        ],
                        choice_hint=(
                            "A normal session is mostly navigation first, then "
                            "processing one chunk at a time."
                        ),
                        success_condition=(
                            "You understand what each dashboard section is for."
                        ),
                        why=(
                            "If the session layout is unclear, the command "
                            "workflow will feel arbitrary."
                        ),
                        completed=False,
                        detail="read the dashboard layout, then type `tutorial next`",
                    ),
                    TutorialStepView(
                        key="workflow_overview",
                        title="Learn the chunk workflow",
                        command="tutorial next",
                        actions=[
                            "The normal loop is: pick a chunk, extract, "
                            "optionally refine in chat, promote, then "
                            "optionally publish.",
                            "You repeat that loop chunk by chunk for one source.",
                            "When you are ready to try that flow on the tutorial "
                            "source, type `tutorial next`.",
                        ],
                        choice_hint=(
                            "Publishing is optional at the workflow level, but "
                            "this tutorial goes through it once so you can "
                            "practice the full path."
                        ),
                        success_condition=(
                            "You understand the order of the main chunk-processing "
                            "commands."
                        ),
                        why=(
                            "Putonghua is designed around a repeatable chunk "
                            "workflow, not around bulk processing a whole source "
                            "at once."
                        ),
                        completed=False,
                        detail="read the workflow summary, then type `tutorial next`",
                    ),
                    TutorialStepView(
                        key="chunk_selected",
                        title="Select the next chunk to process",
                        command="n",
                        actions=[
                            "Type `n` to jump to the next pending chunk in the "
                            "tutorial source.",
                            "Check the `Chunks` table and confirm the pending "
                            "chunk now has the selection marker.",
                            "Check the `Focus` panel now shows that selected chunk.",
                        ],
                        choice_hint=(
                            "When you start real work, `n` is the fastest way to "
                            "move to the next unfinished chunk."
                        ),
                        success_condition=(
                            "Dashboard focus moves to the pending tutorial chunk."
                        ),
                        why=(
                            "The chunk is the unit of work. Everything else in the "
                            "session hangs off the selected chunk."
                        ),
                        completed=False,
                        detail=(
                            "no chunk selected yet; use `n` to focus the pending "
                            "tutorial chunk"
                        ),
                    ),
                    TutorialStepView(
                        key="candidates_extracted",
                        title="Extract candidate cards",
                        command="extract",
                        actions=[
                            "Leave the pending tutorial chunk selected.",
                            "Type `extract` and wait for the extraction result "
                            "message.",
                            "Check that the chunk or source candidate count is now "
                            "above zero.",
                        ],
                        choice_hint=(
                            "After extraction, you can either promote a simple "
                            "candidate directly or use `chat` first if you want "
                            "refinement."
                        ),
                        success_condition=(
                            "The selected chunk has persisted candidate rows."
                        ),
                        why=(
                            "Extraction is the first workflow stage that produces "
                            "durable card data."
                        ),
                        completed=False,
                        detail="no persisted candidates found for chunk -",
                    ),
                    TutorialStepView(
                        key="suggestion_promoted",
                        title="Promote one candidate",
                        command="promote 1",
                        actions=[
                            "Inspect the visible extracted candidates for the chunk.",
                            "If you already like one, run `promote 1` or another "
                            "candidate index.",
                            "If you want refinement first, use `chat`; any new "
                            "chat ideas will appear as additional candidates in "
                            "the same list.",
                            "Check that one durable candidate now exists with "
                            "status `promoted`.",
                        ],
                        choice_hint=(
                            "Simple words and phrases can be promoted directly. "
                            "Use review chat when you want better options, "
                            "comparison, or a stronger sentence card."
                        ),
                        success_condition=(
                            "One candidate for the chunk is marked ready to publish."
                        ),
                        why=(
                            "Promotion is the human review checkpoint between raw "
                            "extraction and the publish queue."
                        ),
                        completed=False,
                        detail="no promoted candidate found yet",
                    ),
                    TutorialStepView(
                        key="candidate_published",
                        title="Publish the candidate",
                        command="publish 1",
                        actions=[
                            "Inspect the visible candidates and choose the promoted "
                            "one you intend to keep.",
                            "Run `publish 1` for the default walkthrough, or another "
                            "index if you chose a different candidate.",
                            "When the confirmation prompt appears, verify the deck "
                            "and note type, then type `y` only if they look correct.",
                        ],
                        choice_hint=(
                            "The final choice is explicit confirmation. Cancel if "
                            "the card or Anki target looks wrong; confirm only "
                            "when you would really publish it."
                        ),
                        success_condition=(
                            "A local publication record exists and Anki returns a "
                            "note id."
                        ),
                        why=(
                            "Publishing closes the loop and proves the real Anki "
                            "integration is working."
                        ),
                        completed=False,
                        detail=(
                            "no published tutorial candidate found with an Anki note id"
                        ),
                    ),
                ],
            )

        def get_dashboard(
            self,
            *,
            selected_project_id: str | None = None,
            selected_source_id: str | None = None,
            selected_chunk_id: str | None = None,
        ):
            from putonghua.models.tui import (
                TuiChunkView,
                TuiDashboardView,
                TuiProjectView,
                TuiSourceView,
            )

            return TuiDashboardView(
                selected_project_id=selected_project_id or "project-1",
                selected_source_id=selected_source_id or "source-1",
                selected_chunk_id=selected_chunk_id or "chunk-2",
                projects=[TuiProjectView("project-1", "Tutorial Project", 1)],
                sources=[
                    TuiSourceView(
                        "source-1",
                        "project-1",
                        "Tutorial Episode",
                        "tutorial_seed",
                        "tutorial_seed",
                        0,
                        2,
                        1,
                    )
                ],
                chunks=[
                    TuiChunkView(
                        "chunk-1",
                        "source-1",
                        0,
                        "completed",
                        7,
                        0,
                        0.0,
                        4.0,
                        "欢迎来到教程。",
                    ),
                    TuiChunkView(
                        "chunk-2",
                        "source-1",
                        1,
                        "pending",
                        27,
                        0,
                        4.0,
                        28.0,
                        "我们从真实工作流开始。",
                    ),
                ],
                candidates=[],
                review_context=None,
                publish_target=None,
                tutorial=self.session if self.active else None,
            )

        def start_tutorial(self) -> TutorialSessionView:
            self.active = True
            return self.session

        def resume_tutorial(self) -> TutorialSessionView:
            self.active = True
            return self.session

        def get_tutorial_session(self) -> TutorialSessionView | None:
            return self.session if self.active else None

        def advance_tutorial(self) -> TutorialSessionView:
            if self.session.current_step == "session_layout":
                updated_steps = [
                    replace(step, completed=(step.key == "session_layout"))
                    if step.key == "session_layout"
                    else step
                    for step in self.session.steps
                ]
                self.session = replace(
                    self.session,
                    current_step="workflow_overview",
                    steps=updated_steps,
                )
            return self.session

        def reset_tutorial(self) -> bool:
            self.active = False
            return True

    commands = iter(
        [
            "tutorial",
            "tutorial next",
            "tutorial status",
            "tutorial reset",
            "tutorial status",
            "quit",
        ]
    )
    output = StringIO()
    console = Console(file=output, force_terminal=False, color_system=None)

    run_tui_session(
        service=cast(TuiSessionService, _FakeService()),
        console=console,
        input_func=lambda _: next(commands),
    )

    rendered = output.getvalue()
    assert "Tutorial started from step 1." in rendered
    assert "Step: 1/6" in rendered
    assert "Goal: Understand the session layout" in rendered
    assert "Command: tutorial next" in rendered
    assert "Do this:" in rendered
    assert "Tutorial advanced." in rendered
    assert "Goal: Learn the chunk workflow" in rendered
    assert "Tutorial state reset." in rendered
    assert "Type `tutorial` to start again from step 1." in rendered
    assert "No active tutorial session." in rendered
    assert "Status: inactive" in rendered
    assert "Command: tutorial" in rendered


def test_run_tui_session_renders_tutorial_panel_once_on_start() -> None:
    class _FakeService:
        def __init__(self) -> None:
            self.active = False
            self.session = TutorialSessionView(
                id="tutorial-session-1",
                status="active",
                current_step="session_layout",
                project_id="project-1",
                source_id="source-1",
                study_chunk_id=None,
                review_conversation_id=None,
                review_suggestion_id=None,
                candidate_card_id=None,
                publication_record_id=None,
                completed_at=None,
                steps=[
                    TutorialStepView(
                        key="session_layout",
                        title="Understand the session layout",
                        command="tutorial next",
                        actions=["Look at the dashboard areas."],
                        choice_hint="Navigation comes first.",
                        success_condition=(
                            "You understand what each dashboard section is for."
                        ),
                        why="The tutorial stays inside the real workflow.",
                        completed=False,
                        detail="read the dashboard layout, then type `tutorial next`",
                    )
                ],
            )

        def get_dashboard(
            self,
            *,
            selected_project_id: str | None = None,
            selected_source_id: str | None = None,
            selected_chunk_id: str | None = None,
        ):
            from putonghua.models.tui import TuiDashboardView

            return TuiDashboardView(
                selected_project_id=selected_project_id or "project-1",
                selected_source_id=selected_source_id or "source-1",
                selected_chunk_id=selected_chunk_id,
                projects=[],
                sources=[],
                chunks=[],
                candidates=[],
                review_context=None,
                publish_target=None,
                tutorial=self.session if self.active else None,
            )

        def start_tutorial(self) -> TutorialSessionView:
            self.active = True
            return self.session

        def resume_tutorial(self) -> TutorialSessionView:
            self.active = True
            return self.session

    commands = iter(["tutorial", "quit"])
    output = StringIO()
    console = Console(file=output, force_terminal=False, color_system=None)

    run_tui_session(
        service=cast(TuiSessionService, _FakeService()),
        console=console,
        input_func=lambda _: next(commands),
    )

    rendered = output.getvalue()
    assert rendered.count("Goal: Understand the session layout") == 1


def test_run_tui_session_renders_inactive_tutorial_guidance() -> None:
    class _FakeService:
        def get_dashboard(
            self,
            *,
            selected_project_id: str | None = None,
            selected_source_id: str | None = None,
            selected_chunk_id: str | None = None,
        ):
            from putonghua.models.tui import TuiDashboardView

            return TuiDashboardView(
                selected_project_id=selected_project_id,
                selected_source_id=selected_source_id,
                selected_chunk_id=selected_chunk_id,
                projects=[],
                sources=[],
                chunks=[],
                candidates=[],
                review_context=None,
                publish_target=None,
                tutorial=None,
            )

    commands = iter(["quit"])
    output = StringIO()
    console = Console(file=output, force_terminal=False, color_system=None)

    run_tui_session(
        service=cast(TuiSessionService, _FakeService()),
        console=console,
        input_func=lambda _: next(commands),
    )

    rendered = output.getvalue()
    assert "Status: inactive" in rendered
    assert "Command: tutorial" in rendered
    assert "tutorial resume" in rendered
