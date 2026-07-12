"""Interactive terminal session helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from putonghua.database.connection import connect
from putonghua.database.migrations import migrate_database
from putonghua.database.repositories import (
    CandidateRepository,
    ProjectRepository,
    PublicationRecordRepository,
    ReviewConversationRepository,
    SourceRepository,
    StudyChunkRepository,
)
from putonghua.models.candidates import (
    CandidateExtractionResult,
    CandidatePromotionResult,
    CandidatePublishResult,
)
from putonghua.models.review import ChunkChatResult
from putonghua.models.tui import (
    TuiCandidateView,
    TuiChunkView,
    TuiDashboardView,
    TuiProjectView,
    TuiPublishTargetView,
    TuiReviewContextView,
    TuiReviewMessageView,
    TuiSourceView,
)
from putonghua.models.tutorial import TutorialSessionView
from putonghua.services.candidate_extraction import CandidateExtractionService
from putonghua.services.candidate_promotion import CandidatePromotionService
from putonghua.services.candidate_publish import CandidatePublishService
from putonghua.services.chunk_review import ChunkReviewService
from putonghua.services.review_suggestions import ReviewSuggestionService
from putonghua.services.study_chunks import StudyChunkService
from putonghua.services.tutorial import TutorialService


@dataclass(frozen=True)
class TuiSessionService:
    """Build read models and run selected in-session workflow actions."""

    database_path: Path
    extraction_service: CandidateExtractionService | None = None
    review_service: ChunkReviewService | None = None
    publish_service: CandidatePublishService | None = None
    publish_target: TuiPublishTargetView | None = None
    tutorial_service: TutorialService | None = None

    def get_dashboard(
        self,
        *,
        selected_project_id: str | None = None,
        selected_source_id: str | None = None,
        selected_chunk_id: str | None = None,
    ) -> TuiDashboardView:
        """Return the current dashboard with stable selection fallback."""

        migrate_database(self.database_path)
        with connect(self.database_path) as connection:
            tutorial_session = self._refresh_tutorial_session(
                selected_chunk_id=selected_chunk_id,
            )
            project_repository = ProjectRepository(connection)
            source_repository = SourceRepository(connection)
            chunk_repository = StudyChunkRepository(connection)
            candidate_repository = CandidateRepository(connection)
            publication_repository = PublicationRecordRepository(connection)
            conversation_repository = ReviewConversationRepository(connection)

            projects = [
                TuiProjectView(
                    id=row.id,
                    name=row.name,
                    source_count=row.source_count,
                )
                for row in project_repository.list_projects()
            ]
            tutorial_project_id = (
                tutorial_session.project_id if tutorial_session is not None else None
            )
            resolved_project_id = _resolve_selected_id(
                tutorial_project_id or selected_project_id,
                [project.id for project in projects],
            )

            sources = [
                TuiSourceView(
                    id=row.id,
                    project_id=row.project_id,
                    title=row.title,
                    source_type=row.source_type,
                    transcript_source=row.transcript_source,
                    candidate_count=row.candidate_count,
                    chunk_count=row.chunk_count,
                    pending_chunk_count=row.pending_chunk_count,
                )
                for row in (
                    source_repository.list_sources_for_project(resolved_project_id)
                    if resolved_project_id is not None
                    else []
                )
            ]
            tutorial_source_id = (
                tutorial_session.source_id if tutorial_session is not None else None
            )
            resolved_source_id = _resolve_selected_id(
                tutorial_source_id or selected_source_id,
                [source.id for source in sources],
            )

            chunks = [
                TuiChunkView(
                    id=row.id,
                    source_id=row.source_id,
                    chunk_index=row.chunk_index,
                    status=row.status,
                    char_count=row.char_count,
                    candidate_count=row.candidate_count,
                    start_seconds=row.start_seconds,
                    end_seconds=row.end_seconds,
                    text=row.text,
                )
                for row in (
                    chunk_repository.list_chunks_for_source(resolved_source_id)
                    if resolved_source_id is not None
                    else []
                )
            ]
            tutorial_chunk_id = (
                tutorial_session.study_chunk_id
                if tutorial_session is not None
                else None
            )
            resolved_chunk_id = _resolve_selected_id(
                selected_chunk_id or tutorial_chunk_id,
                [chunk.id for chunk in chunks],
            )
            candidates = _build_candidate_views(
                candidate_repository=candidate_repository,
                publication_repository=publication_repository,
                resolved_chunk_id=resolved_chunk_id,
            )
            review_context = _build_review_context(
                conversation_repository=conversation_repository,
                resolved_chunk_id=resolved_chunk_id,
            )

        return TuiDashboardView(
            selected_project_id=resolved_project_id,
            selected_source_id=resolved_source_id,
            selected_chunk_id=resolved_chunk_id,
            projects=projects,
            sources=sources,
            chunks=chunks,
            candidates=candidates,
            review_context=review_context,
            publish_target=self.publish_target,
            tutorial=tutorial_session,
        )

    def extract_chunk(self, chunk_id: str) -> CandidateExtractionResult:
        """Run candidate extraction for one selected chunk."""

        if self.extraction_service is None:
            message = "Chunk extraction requires OPENAI_API_KEY or openai.api_key."
            raise ValueError(message)
        return self.extraction_service.extract_for_chunk(chunk_id)

    def chat_for_chunk(self, chunk_id: str, prompt: str) -> ChunkChatResult:
        """Run one review chat turn for one selected chunk."""

        if self.review_service is None:
            message = "Chunk chat requires OPENAI_API_KEY or openai.api_key."
            raise ValueError(message)
        return self.review_service.chat_for_chunk(chunk_id, prompt)

    def promote_suggestion(self, suggestion_id: str) -> CandidatePromotionResult:
        """Promote one stored review suggestion into a durable candidate."""

        return ReviewSuggestionService(self.database_path).promote_suggestion(
            suggestion_id
        )

    def promote_candidate(self, candidate_id: str) -> CandidatePromotionResult:
        """Promote one extracted candidate directly."""

        return CandidatePromotionService(self.database_path).promote_candidate(
            candidate_id
        )

    def publish_candidate(self, candidate_id: str) -> CandidatePublishResult:
        """Publish one durable candidate from the current chunk."""

        if self.publish_service is None:
            message = (
                "Candidate publish requires anki.default_deck and "
                "anki.default_note_type."
            )
            raise ValueError(message)
        return self.publish_service.publish_candidate(candidate_id)

    def complete_chunk(self, chunk_id: str) -> None:
        """Mark one selected chunk completed."""

        StudyChunkService(database_path=self.database_path).update_chunk_status(
            chunk_id,
            "completed",
        )

    def start_tutorial(self) -> TutorialSessionView:
        """Start a fresh dedicated tutorial session from step one."""

        if self.tutorial_service is None:
            message = "Tutorial support is not configured for this TUI session."
            raise ValueError(message)
        return self.tutorial_service.start_fresh_session()

    def resume_tutorial(self) -> TutorialSessionView:
        """Resume the active tutorial session, or create one if absent."""

        if self.tutorial_service is None:
            message = "Tutorial support is not configured for this TUI session."
            raise ValueError(message)
        return self.tutorial_service.ensure_active_session()

    def get_tutorial_session(self) -> TutorialSessionView | None:
        """Return the active tutorial session, if any."""

        if self.tutorial_service is None:
            return None
        try:
            return self.tutorial_service.get_active_session()
        except ValueError:
            return None

    def reset_tutorial(self) -> bool:
        """Reset the active tutorial session, if present."""

        if self.tutorial_service is None:
            message = "Tutorial support is not configured for this TUI session."
            raise ValueError(message)
        return self.tutorial_service.reset_active_session()

    def advance_tutorial(self) -> TutorialSessionView:
        """Advance one manual tutorial step."""

        if self.tutorial_service is None:
            message = "Tutorial support is not configured for this TUI session."
            raise ValueError(message)
        return self.tutorial_service.advance_active_session()

    def _refresh_tutorial_session(
        self,
        *,
        selected_chunk_id: str | None,
    ) -> TutorialSessionView | None:
        """Return the active tutorial session with refreshed progress."""

        if self.tutorial_service is None:
            return None
        active_session = self.tutorial_service.get_active_session()
        if active_session is None:
            return None
        try:
            return self.tutorial_service.refresh_active_session(
                project_id=active_session.project_id,
                source_id=active_session.source_id,
                study_chunk_id=selected_chunk_id or active_session.study_chunk_id,
            )
        except ValueError:
            return None


def _resolve_selected_id(
    selected_id: str | None,
    available_ids: list[str],
) -> str | None:
    """Return a stable selected id for a dashboard list."""

    if not available_ids:
        return None
    if selected_id in available_ids:
        return selected_id
    return available_ids[0]


def _build_review_context(
    *,
    conversation_repository: ReviewConversationRepository,
    resolved_chunk_id: str | None,
) -> TuiReviewContextView | None:
    """Return the latest persisted review context for the selected chunk."""

    if resolved_chunk_id is None:
        return None

    conversation = conversation_repository.get_latest_for_chunk(resolved_chunk_id)
    if conversation is None:
        return None

    return TuiReviewContextView(
        conversation_id=conversation.id,
        messages=[
            TuiReviewMessageView(
                role=message.role,
                content=message.content,
            )
            for message in conversation_repository.list_messages(conversation.id)
        ],
    )


def _build_candidate_views(
    *,
    candidate_repository: CandidateRepository,
    publication_repository: PublicationRecordRepository,
    resolved_chunk_id: str | None,
) -> list[TuiCandidateView]:
    """Return stored candidates for the selected chunk with publish metadata."""

    if resolved_chunk_id is None:
        return []

    candidates = candidate_repository.list_candidates_for_chunk(resolved_chunk_id)
    views: list[TuiCandidateView] = []
    for candidate in candidates:
        publication = publication_repository.get_by_candidate_id(candidate.id)
        views.append(
            TuiCandidateView(
                id=candidate.id,
                candidate_type=candidate.candidate_type,
                simplified=candidate.simplified,
                english=candidate.english,
                status=candidate.status,
                publication_status=(
                    publication.status if publication is not None else None
                ),
                anki_note_id=(
                    int(publication.anki_note_id)
                    if publication is not None and publication.anki_note_id is not None
                    else None
                ),
            )
        )
    return views
