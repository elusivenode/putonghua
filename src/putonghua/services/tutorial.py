"""Tutorial session persistence and progress detection."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from putonghua.database.connection import connect
from putonghua.database.migrations import migrate_database
from putonghua.database.repositories import (
    CandidateRepository,
    ProjectRepository,
    PublicationRecordRepository,
    ReviewConversationRepository,
    ReviewSuggestionRepository,
    SourceCreateRecord,
    SourceRepository,
    StudyChunkRecord,
    StudyChunkRepository,
    TranscriptSegmentRecord,
    TutorialSessionRepository,
    TutorialSessionRow,
)
from putonghua.models.tutorial import (
    TUTORIAL_STEP_ORDER,
    TutorialSessionView,
    TutorialStepKey,
    TutorialStepView,
)

MANUAL_TUTORIAL_STEPS: tuple[TutorialStepKey, ...] = (
    "session_layout",
    "workflow_overview",
)


@dataclass(frozen=True)
class _TutorialStepCopy:
    """Operator-facing copy for one tutorial step."""

    title: str
    command: str
    actions: tuple[str, ...]
    choice_hint: str
    success_condition: str
    why: str


STEP_COPY: dict[TutorialStepKey, _TutorialStepCopy] = {
    "session_layout": _TutorialStepCopy(
        title="Understand the session layout",
        command="tutorial next",
        actions=(
            "Look at the four main areas: Projects, Sources, Chunks, and Focus.",
            "Projects contain sources. Sources contain chunks. Focus shows the "
            "selected chunk details.",
            "When that mental model makes sense, type `tutorial next`.",
        ),
        choice_hint=(
            "A normal session is mostly navigation first, then processing one "
            "chunk at a time."
        ),
        success_condition="You understand what each dashboard section is for.",
        why=(
            "If the session layout is unclear, the command workflow will feel "
            "arbitrary."
        ),
    ),
    "workflow_overview": _TutorialStepCopy(
        title="Learn the chunk workflow",
        command="tutorial next",
        actions=(
            "The normal loop is: pick a chunk, extract, optionally refine in "
            "chat, promote, then optionally publish.",
            "You repeat that loop chunk by chunk for one source.",
            "When you are ready to try that flow on the tutorial source, "
            "type `tutorial next`.",
        ),
        choice_hint=(
            "Publishing is optional at the workflow level, but this tutorial "
            "goes through it once so you can practice the full path."
        ),
        success_condition=(
            "You understand the order of the main chunk-processing commands."
        ),
        why=(
            "Putonghua is designed around a repeatable chunk workflow, not "
            "around bulk processing a whole source at once."
        ),
    ),
    "chunk_selected": _TutorialStepCopy(
        title="Select the next chunk to process",
        command="n",
        actions=(
            "Type `n` to jump to the next pending chunk in the tutorial source.",
            "Check the `Chunks` table and confirm the pending chunk now has "
            "the selection marker.",
            "Check the `Focus` panel now shows that selected chunk.",
        ),
        choice_hint=(
            "When you start real work, `n` is the fastest way to move to the "
            "next unfinished chunk."
        ),
        success_condition="Dashboard focus moves to the pending tutorial chunk.",
        why=(
            "The chunk is the unit of work. Everything else in the session "
            "hangs off the selected chunk."
        ),
    ),
    "candidates_extracted": _TutorialStepCopy(
        title="Extract candidate cards",
        command="extract",
        actions=(
            "Leave the selected tutorial chunk selected.",
            "Type `extract` and wait for the extraction result message.",
            "Check that the chunk or source candidate count is now above zero.",
        ),
        choice_hint=(
            "After extraction, you can either promote a simple candidate "
            "directly or use `chat` first if you want refinement."
        ),
        success_condition="The selected chunk has persisted candidate rows.",
        why="Extraction is the first workflow stage that produces durable card data.",
    ),
    "suggestion_promoted": _TutorialStepCopy(
        title="Promote one candidate",
        command="promote 1",
        actions=(
            "Inspect the visible extracted candidates for the chunk.",
            "If you already like one, run `promote 1` or another candidate index.",
            "If you want refinement first, use `chat`; any new chat ideas will "
            "appear as additional candidates in the same list.",
            "Check that one durable candidate now exists with status `promoted`.",
        ),
        choice_hint=(
            "Simple words and phrases can be promoted directly. Use review chat "
            "when you want better options, comparison, or a stronger sentence card."
        ),
        success_condition=("One candidate for the chunk is marked ready to publish."),
        why=(
            "Promotion is the human review checkpoint between raw extraction "
            "and the publish queue."
        ),
    ),
    "candidate_published": _TutorialStepCopy(
        title="Publish the candidate",
        command="publish 1",
        actions=(
            "Inspect the visible candidates and choose the promoted one you "
            "intend to keep.",
            "Run `publish 1` for the default walkthrough, or another index "
            "if you chose a different candidate.",
            "When the confirmation prompt appears, verify the deck and note "
            "type, then type `y` only if they look correct.",
        ),
        choice_hint=(
            "The final choice is explicit confirmation. Cancel if the card or Anki "
            "target looks wrong; confirm only when you would really publish it."
        ),
        success_condition=(
            "A local publication record exists and Anki returns a note id."
        ),
        why=(
            "Publishing closes the loop and proves the real Anki integration "
            "is working."
        ),
    ),
}

TUTORIAL_PROJECT_NAME = "Putonghua Tutorial"
TUTORIAL_SOURCE_TITLE = "Putonghua Tutorial: Real Workflow"
TUTORIAL_SOURCE_CONTENT_HASH = "putonghua-tutorial-sample-v1"
TUTORIAL_SOURCE_TYPE = "tutorial_seed"
TUTORIAL_SOURCE_ORIGINAL_PATH = "local://putonghua/tutorial-source-v1"
TUTORIAL_SOURCE_EXTERNAL_ID = "tutorial-source-v1"
TUTORIAL_SOURCE_MEDIA_PATH = "local://putonghua/tutorial-source-v1.webm"
TUTORIAL_TRANSCRIPT_SOURCE = "tutorial_seed"
TUTORIAL_TRANSCRIPT_TEXT = (
    "欢迎来到教程。我们从真实工作流开始。先选中这个教程分块，然后提取候选卡片。"
)
TUTORIAL_TRANSCRIPT_SEGMENTS: tuple[TranscriptSegmentRecord, ...] = (
    TranscriptSegmentRecord(0.0, 4.0, "欢迎来到教程。", 0),
    TranscriptSegmentRecord(
        4.0,
        16.0,
        "我们从真实工作流开始。",
        1,
    ),
    TranscriptSegmentRecord(
        16.0,
        28.0,
        "先选中这个教程分块，然后提取候选卡片。",
        2,
    ),
)
TUTORIAL_CHUNKS: tuple[StudyChunkRecord, ...] = (
    StudyChunkRecord(
        source_id="",
        chunk_index=0,
        start_seconds=0.0,
        end_seconds=4.0,
        text="欢迎来到教程。",
        transcript_segment_count=1,
        char_count=7,
        status="completed",
    ),
    StudyChunkRecord(
        source_id="",
        chunk_index=1,
        start_seconds=4.0,
        end_seconds=28.0,
        text="我们从真实工作流开始。先选中这个教程分块，然后提取候选卡片。",
        transcript_segment_count=2,
        char_count=27,
        status="pending",
    ),
)


@dataclass(frozen=True)
class TutorialService:
    """Manage one persisted tutorial session and derive real progress."""

    database_path: Path

    def start_fresh_session(self) -> TutorialSessionView:
        """Reset tutorial-only workflow state and start from step one."""

        migrate_database(self.database_path)
        with connect(self.database_path) as connection:
            repository = TutorialSessionRepository(connection)
            active_session = repository.get_active_session()
            if active_session is not None:
                repository.mark_reset(active_session.id)

            project_id, source_id = self._ensure_tutorial_workspace(connection)
            self._reset_tutorial_workspace(connection, source_id)

            session_id = repository.create_session(
                current_step="session_layout",
                project_id=project_id,
                source_id=source_id,
                study_chunk_id=None,
            )
            connection.commit()

            session = repository.get_session(session_id)
            if session is None:
                message = "Fresh tutorial session was not persisted correctly."
                raise RuntimeError(message)

        return self.refresh_active_session(project_id=project_id, source_id=source_id)

    def ensure_active_session(
        self,
        *,
        project_id: str | None = None,
        source_id: str | None = None,
        study_chunk_id: str | None = None,
    ) -> TutorialSessionView:
        """Return one active tutorial session, creating it if needed."""

        migrate_database(self.database_path)
        with connect(self.database_path) as connection:
            repository = TutorialSessionRepository(connection)
            session = repository.get_active_session()
            if session is None:
                if project_id is None and source_id is None and study_chunk_id is None:
                    resolved_project_id, resolved_source_id = (
                        self._ensure_tutorial_workspace(connection)
                    )
                    resolved_chunk_id = None
                else:
                    resolved_project_id, resolved_source_id, resolved_chunk_id = (
                        self._resolve_context(
                            connection,
                            project_id=project_id,
                            source_id=source_id,
                            study_chunk_id=study_chunk_id,
                        )
                    )
                initial_step = (
                    "session_layout" if resolved_chunk_id is None else "chunk_selected"
                )
                session_id = repository.create_session(
                    current_step=initial_step,
                    project_id=resolved_project_id,
                    source_id=resolved_source_id,
                    study_chunk_id=resolved_chunk_id,
                )
                session = repository.get_active_session()
                if session is None or session.id != session_id:
                    message = "Tutorial session was not persisted correctly."
                    raise RuntimeError(message)

        return self.refresh_active_session(
            project_id=project_id,
            source_id=source_id,
            study_chunk_id=study_chunk_id,
        )

    def get_active_session(self) -> TutorialSessionView | None:
        """Return the active tutorial session with refreshed progress."""

        migrate_database(self.database_path)
        with connect(self.database_path) as connection:
            session = TutorialSessionRepository(connection).get_active_session()
            if session is None:
                return None
        return self.refresh_active_session()

    def refresh_active_session(
        self,
        *,
        project_id: str | None = None,
        source_id: str | None = None,
        study_chunk_id: str | None = None,
    ) -> TutorialSessionView:
        """Refresh progress for the active tutorial session."""

        migrate_database(self.database_path)
        with connect(self.database_path) as connection:
            repository = TutorialSessionRepository(connection)
            session = repository.get_active_session()
            if session is None:
                message = "No active tutorial session found."
                raise ValueError(message)

            resolved_project_id, resolved_source_id, resolved_chunk_id = (
                self._resolve_context(
                    connection,
                    project_id=project_id or session.project_id,
                    source_id=source_id or session.source_id,
                    study_chunk_id=study_chunk_id or session.study_chunk_id,
                )
            )
            progress = self._build_progress(
                connection,
                session=session,
                project_id=resolved_project_id,
                source_id=resolved_source_id,
                study_chunk_id=resolved_chunk_id,
            )
            repository.update_session(
                session.id,
                status=progress.status,
                current_step=progress.current_step,
                project_id=resolved_project_id,
                source_id=resolved_source_id,
                study_chunk_id=resolved_chunk_id,
                review_conversation_id=progress.review_conversation_id,
                review_suggestion_id=progress.review_suggestion_id,
                candidate_card_id=progress.candidate_card_id,
                publication_record_id=progress.publication_record_id,
                completed_at=progress.completed_at,
            )
            connection.commit()

            refreshed = repository.get_session(session.id)
            if refreshed is None:
                message = "Tutorial session disappeared during refresh."
                raise RuntimeError(message)
            return TutorialSessionView(
                id=refreshed.id,
                status=refreshed.status,
                current_step=refreshed.current_step,
                project_id=refreshed.project_id,
                source_id=refreshed.source_id,
                study_chunk_id=refreshed.study_chunk_id,
                review_conversation_id=refreshed.review_conversation_id,
                review_suggestion_id=refreshed.review_suggestion_id,
                candidate_card_id=refreshed.candidate_card_id,
                publication_record_id=refreshed.publication_record_id,
                completed_at=refreshed.completed_at,
                steps=progress.steps,
            )

    def reset_active_session(self) -> bool:
        """Reset the currently active tutorial session."""

        migrate_database(self.database_path)
        with connect(self.database_path) as connection:
            repository = TutorialSessionRepository(connection)
            session = repository.get_active_session()
            if session is not None:
                repository.mark_reset(session.id)

            source = SourceRepository(connection).get_source_by_content_hash(
                TUTORIAL_SOURCE_CONTENT_HASH
            )
            if source is not None:
                self._reset_tutorial_workspace(connection, source.id)

            connection.commit()
            return session is not None

    def advance_active_session(self) -> TutorialSessionView:
        """Advance one manual tutorial step."""

        migrate_database(self.database_path)
        with connect(self.database_path) as connection:
            repository = TutorialSessionRepository(connection)
            session = repository.get_active_session()
            if session is None:
                raise ValueError("No active tutorial session found.")
            if session.current_step not in MANUAL_TUTORIAL_STEPS:
                raise ValueError(
                    "The current tutorial step advances through real workflow state."
                )
            next_step = _next_step_key(session.current_step)
            repository.update_session(
                session.id,
                status=session.status,
                current_step=next_step,
                project_id=session.project_id,
                source_id=session.source_id,
                study_chunk_id=session.study_chunk_id,
                review_conversation_id=session.review_conversation_id,
                review_suggestion_id=session.review_suggestion_id,
                candidate_card_id=session.candidate_card_id,
                publication_record_id=session.publication_record_id,
                completed_at=session.completed_at,
            )
            connection.commit()
        return self.refresh_active_session()

    def _resolve_context(
        self,
        connection: sqlite3.Connection,
        *,
        project_id: str | None,
        source_id: str | None,
        study_chunk_id: str | None,
    ) -> tuple[str | None, str | None, str | None]:
        """Resolve a consistent tutorial project/source/chunk triple."""

        chunk_repository = StudyChunkRepository(connection)
        source_repository = SourceRepository(connection)

        resolved_project_id = project_id
        resolved_source_id = source_id
        resolved_chunk_id = study_chunk_id

        if resolved_chunk_id is not None:
            chunk = chunk_repository.get_chunk(resolved_chunk_id)
            if chunk is not None:
                resolved_source_id = chunk.source_id
                source = source_repository.get_source_context(chunk.source_id)
                if source is not None:
                    resolved_project_id = source.project_id
                    return resolved_project_id, resolved_source_id, resolved_chunk_id

        if resolved_source_id is not None:
            source = source_repository.get_source_context(resolved_source_id)
            if source is not None:
                resolved_project_id = source.project_id

        return resolved_project_id, resolved_source_id, resolved_chunk_id

    def _ensure_tutorial_workspace(
        self,
        connection: sqlite3.Connection,
    ) -> tuple[str, str]:
        """Create or reuse the dedicated tutorial project and source."""

        project_repository = ProjectRepository(connection)
        source_repository = SourceRepository(connection)
        chunk_repository = StudyChunkRepository(connection)

        project = project_repository.get_or_create_by_name(TUTORIAL_PROJECT_NAME)
        source = source_repository.get_source_by_content_hash(
            TUTORIAL_SOURCE_CONTENT_HASH
        )
        if source is None:
            source_id = source_repository.create_source(
                SourceCreateRecord(
                    project_id=project.id,
                    source_type=TUTORIAL_SOURCE_TYPE,
                    title=TUTORIAL_SOURCE_TITLE,
                    content_hash=TUTORIAL_SOURCE_CONTENT_HASH,
                    original_path=TUTORIAL_SOURCE_ORIGINAL_PATH,
                    external_id=TUTORIAL_SOURCE_EXTERNAL_ID,
                    channel_name=TUTORIAL_PROJECT_NAME,
                    published_at=None,
                    media_path=TUTORIAL_SOURCE_MEDIA_PATH,
                    transcript_source=TUTORIAL_TRANSCRIPT_SOURCE,
                    transcript_text=TUTORIAL_TRANSCRIPT_TEXT,
                    metadata={
                        "tutorial": True,
                        "tutorial_version": 1,
                    },
                ),
                list(TUTORIAL_TRANSCRIPT_SEGMENTS),
            )
        else:
            source_id = source.id

        if not chunk_repository.list_chunks_for_source(source_id):
            chunk_repository.replace_for_source(
                source_id,
                [
                    StudyChunkRecord(
                        source_id=source_id,
                        chunk_index=chunk.chunk_index,
                        start_seconds=chunk.start_seconds,
                        end_seconds=chunk.end_seconds,
                        text=chunk.text,
                        transcript_segment_count=chunk.transcript_segment_count,
                        char_count=chunk.char_count,
                        status=chunk.status,
                    )
                    for chunk in TUTORIAL_CHUNKS
                ],
            )

        return project.id, source_id

    def _build_progress(
        self,
        connection: sqlite3.Connection,
        *,
        session: TutorialSessionRow,
        project_id: str | None,
        source_id: str | None,
        study_chunk_id: str | None,
    ) -> _TutorialProgress:
        """Build the latest tutorial completion state from persisted rows."""

        candidate_repository = CandidateRepository(connection)
        conversation_repository = ReviewConversationRepository(connection)
        suggestion_repository = ReviewSuggestionRepository(connection)
        publication_repository = PublicationRecordRepository(connection)
        source_repository = SourceRepository(connection)
        chunk_repository = StudyChunkRepository(connection)

        chunk_selected = False
        if (
            project_id is not None
            and source_id is not None
            and study_chunk_id is not None
        ):
            chunk = chunk_repository.get_chunk(study_chunk_id)
            source = source_repository.get_source_context(source_id)
            chunk_selected = (
                chunk is not None
                and source is not None
                and chunk.source_id == source.id
                and chunk.status == "pending"
                and source.project_id == project_id
            )

        candidates_extracted = False
        candidate_count = 0
        review_conversation_id: str | None = None
        review_suggestion_id: str | None = None
        candidate_card_id: str | None = None
        suggestion_promoted = False
        publication_record_id: str | None = None
        publication_status: str | None = None
        publication_note_id: str | None = None
        candidate_published = False

        if study_chunk_id is not None:
            candidates = candidate_repository.list_candidates_for_chunk(study_chunk_id)
            candidate_count = len(candidates)
            candidates_extracted = bool(candidates)

            conversation = conversation_repository.get_latest_for_chunk(study_chunk_id)
            if conversation is not None:
                review_conversation_id = conversation.id

            promoted = suggestion_repository.get_latest_promoted_for_chunk(
                study_chunk_id
            )
            if promoted is not None and promoted.promoted_candidate_card_id is not None:
                review_suggestion_id = promoted.id
                candidate_card_id = promoted.promoted_candidate_card_id
                suggestion_promoted = True
            else:
                for candidate in reversed(candidates):
                    if candidate.status in {"promoted", "published"}:
                        candidate_card_id = candidate.id
                        suggestion_promoted = True
                        break

            if candidate_card_id is not None:
                publication = publication_repository.get_by_candidate_id(
                    candidate_card_id
                )
                if publication is not None:
                    publication_record_id = publication.id
                    publication_status = publication.status
                    publication_note_id = publication.anki_note_id
                    if (
                        publication.status == "published"
                        and publication.anki_note_id is not None
                    ):
                        candidate_published = True

        current_index = _step_index(session.current_step)
        completed = {
            "session_layout": current_index > _step_index("session_layout"),
            "workflow_overview": current_index > _step_index("workflow_overview"),
            "chunk_selected": chunk_selected,
            "candidates_extracted": candidates_extracted,
            "suggestion_promoted": suggestion_promoted,
            "candidate_published": candidate_published,
        }
        steps = [
            self._build_step_view(
                step_key,
                completed=completed[step_key],
                project_id=project_id,
                source_id=source_id,
                study_chunk_id=study_chunk_id,
                candidate_count=candidate_count,
                review_conversation_id=review_conversation_id,
                review_suggestion_id=review_suggestion_id,
                candidate_card_id=candidate_card_id,
                publication_record_id=publication_record_id,
                publication_status=publication_status,
                publication_note_id=publication_note_id,
            )
            for step_key in TUTORIAL_STEP_ORDER
        ]

        current_step = _resolve_current_step(session.current_step, completed)
        status = "completed" if current_step == "completed" else session.status

        return _TutorialProgress(
            status=status,
            current_step=current_step,
            review_conversation_id=review_conversation_id,
            review_suggestion_id=review_suggestion_id,
            candidate_card_id=candidate_card_id,
            publication_record_id=publication_record_id,
            completed_at=session.completed_at,
            steps=steps,
        )

    def _build_step_view(
        self,
        step_key: TutorialStepKey,
        *,
        completed: bool,
        project_id: str | None,
        source_id: str | None,
        study_chunk_id: str | None,
        candidate_count: int,
        review_conversation_id: str | None,
        review_suggestion_id: str | None,
        candidate_card_id: str | None,
        publication_record_id: str | None,
        publication_status: str | None,
        publication_note_id: str | None,
    ) -> TutorialStepView:
        """Build one tutorial step view from the current progress snapshot."""

        copy = STEP_COPY[step_key]
        return TutorialStepView(
            key=step_key,
            title=copy.title,
            command=copy.command,
            actions=list(copy.actions),
            choice_hint=copy.choice_hint,
            success_condition=copy.success_condition,
            why=copy.why,
            completed=completed,
            detail=self._step_detail(
                step_key,
                completed,
                project_id=project_id,
                source_id=source_id,
                study_chunk_id=study_chunk_id,
                candidate_count=candidate_count,
                review_conversation_id=review_conversation_id,
                review_suggestion_id=review_suggestion_id,
                candidate_card_id=candidate_card_id,
                publication_record_id=publication_record_id,
                publication_status=publication_status,
                publication_note_id=publication_note_id,
            ),
        )

    def _step_detail(
        self,
        step_key: TutorialStepKey,
        completed: bool,
        *,
        project_id: str | None,
        source_id: str | None,
        study_chunk_id: str | None,
        candidate_count: int,
        review_conversation_id: str | None,
        review_suggestion_id: str | None,
        candidate_card_id: str | None,
        publication_record_id: str | None,
        publication_status: str | None,
        publication_note_id: str | None,
    ) -> str:
        """Return a compact progress detail for one step."""

        if step_key == "session_layout":
            return (
                "projects, sources, chunks, and focus are visible on screen"
                if completed
                else "read the dashboard layout, then type `tutorial next`"
            )
        if step_key == "workflow_overview":
            return (
                "chunk workflow overview acknowledged"
                if completed
                else "read the workflow summary, then type `tutorial next`"
            )
        if step_key == "chunk_selected":
            if completed:
                return (
                    f"project={project_id}, source={source_id}, chunk={study_chunk_id}"
                )
            if study_chunk_id is None:
                return (
                    "no chunk selected yet; use `n` to focus the pending tutorial chunk"
                )
            if project_id is None or source_id is None:
                return (
                    "tutorial project/source context is unresolved; "
                    "restart with `tutorial`"
                )
            return (
                f"chunk {study_chunk_id} is not aligned with tutorial source "
                f"{source_id}"
            )
        if step_key == "candidates_extracted":
            if study_chunk_id is None:
                return "select the tutorial chunk first, then run `extract`"
            return (
                f"{candidate_count} candidate row(s) exist for chunk {study_chunk_id}"
                if completed
                else (
                    f"no persisted candidates found for chunk {study_chunk_id}; "
                    "run `extract` after provider configuration is ready"
                )
            )
        if step_key == "suggestion_promoted":
            return (
                "candidate="
                f"{candidate_card_id}, suggestion={review_suggestion_id}, "
                f"conversation={review_conversation_id}"
                if completed
                else (
                    "no promoted candidate found yet; run `promote` on a "
                    "candidate, or use `chat` first to add more candidates"
                )
            )
        if candidate_card_id is None:
            return "no promoted candidate is available for publish yet"
        if publication_record_id is not None and publication_note_id is None:
            return (
                f"publication={publication_record_id} is "
                f"{publication_status or 'pending'} "
                "without an Anki note id; check AnkiConnect and retry `publish`"
            )
        return (
            "publication="
            f"{publication_record_id}, candidate={candidate_card_id}, "
            f"note={publication_note_id}"
            if completed
            else (
                "no published tutorial candidate found with an Anki note id; "
                "run `publish` after Anki is ready"
            )
        )

    def _reset_tutorial_workspace(
        self,
        connection: sqlite3.Connection,
        source_id: str,
    ) -> None:
        """Clear tutorial-only workflow artifacts for the seeded source."""

        chunk_repository = StudyChunkRepository(connection)
        publication_repository = PublicationRecordRepository(connection)
        suggestion_repository = ReviewSuggestionRepository(connection)
        conversation_repository = ReviewConversationRepository(connection)
        candidate_repository = CandidateRepository(connection)

        chunk_ids = [
            chunk.id for chunk in chunk_repository.list_chunks_for_source(source_id)
        ]
        publication_repository.delete_for_source(source_id)
        suggestion_repository.delete_for_chunk_ids(chunk_ids)
        conversation_repository.delete_for_chunk_ids(chunk_ids)
        candidate_repository.delete_for_source(source_id)


@dataclass(frozen=True)
class _TutorialProgress:
    """Internal tutorial progress snapshot."""

    status: str
    current_step: str
    review_conversation_id: str | None
    review_suggestion_id: str | None
    candidate_card_id: str | None
    publication_record_id: str | None
    completed_at: str | None
    steps: list[TutorialStepView]


def _step_index(step_key: str) -> int:
    """Return the index of one tutorial step or the terminal position."""

    if step_key == "completed":
        return len(TUTORIAL_STEP_ORDER)
    return TUTORIAL_STEP_ORDER.index(step_key)


def _next_step_key(step_key: TutorialStepKey) -> str:
    """Return the next tutorial step key or completed."""

    next_index = _step_index(step_key) + 1
    if next_index >= len(TUTORIAL_STEP_ORDER):
        return "completed"
    return TUTORIAL_STEP_ORDER[next_index]


def _resolve_current_step(
    stored_step: str,
    completed: dict[TutorialStepKey, bool],
) -> str:
    """Resolve the next visible tutorial step from stored progress and signals."""

    if stored_step == "completed":
        return "completed"
    if stored_step in MANUAL_TUTORIAL_STEPS:
        return stored_step

    current_step = stored_step
    while current_step != "completed" and completed.get(current_step, False):
        current_step = _next_step_key(current_step)
        if current_step in MANUAL_TUTORIAL_STEPS:
            return current_step
    return current_step
