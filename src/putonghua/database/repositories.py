"""Small repositories for the current vertical slice."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from typing import Any
from uuid import uuid4


@dataclass(frozen=True)
class ProjectRecord:
    """Persisted project row."""

    id: str
    name: str


@dataclass(frozen=True)
class TranscriptSegmentRecord:
    """Transcript segment for a source."""

    start_seconds: float
    end_seconds: float
    text: str
    segment_index: int


@dataclass(frozen=True)
class TranscriptSegmentRow:
    """Persisted transcript segment row."""

    id: str
    source_id: str
    start_seconds: float
    end_seconds: float
    text: str
    segment_index: int


@dataclass(frozen=True)
class StudyChunkRecord:
    """Study chunk ready for persistence."""

    source_id: str
    chunk_index: int
    start_seconds: float
    end_seconds: float
    text: str
    transcript_segment_count: int
    char_count: int
    status: str = "pending"
    last_reviewed_at: str | None = None
    notes: str | None = None


@dataclass(frozen=True)
class StudyChunkRow:
    """Persisted study chunk row."""

    id: str
    source_id: str
    chunk_index: int
    start_seconds: float
    end_seconds: float
    text: str
    transcript_segment_count: int
    char_count: int
    status: str
    last_reviewed_at: str | None
    notes: str | None


@dataclass(frozen=True)
class SourceCreateRecord:
    """Payload for inserting a source."""

    project_id: str
    source_type: str
    title: str
    content_hash: str
    original_path: str
    external_id: str | None
    channel_name: str | None
    published_at: str | None
    media_path: str | None
    transcript_source: str | None
    transcript_text: str | None
    metadata: dict[str, Any]


@dataclass(frozen=True)
class SourceContextRow:
    """Minimal source context needed for downstream extraction."""

    id: str
    project_id: str
    title: str


@dataclass(frozen=True)
class CandidateCardCreateRecord:
    """Payload for inserting one candidate card."""

    project_id: str
    source_id: str
    study_chunk_id: str
    candidate_type: str
    simplified: str
    traditional: str
    pinyin: str
    english: str
    provenance: dict[str, Any]
    status: str = "proposed"


@dataclass(frozen=True)
class CandidateCardRow:
    """Persisted candidate card row."""

    id: str
    project_id: str
    source_id: str
    study_chunk_id: str | None
    candidate_type: str
    status: str
    simplified: str | None
    traditional: str | None
    pinyin: str | None
    english: str | None
    provenance_json: str


@dataclass(frozen=True)
class ReviewConversationRow:
    """Persisted review conversation row."""

    id: str
    study_chunk_id: str
    provider: str
    model: str
    prompt_version: str


@dataclass(frozen=True)
class ReviewMessageRow:
    """Persisted review message row."""

    id: str
    conversation_id: str
    role: str
    content: str


@dataclass(frozen=True)
class ReviewSuggestionCreateRecord:
    """Payload for inserting one structured review suggestion."""

    conversation_id: str
    study_chunk_id: str
    source_message_id: str
    suggestion_index: int
    candidate_type: str
    simplified: str
    traditional: str
    pinyin: str
    english: str
    rationale: str
    source_excerpt: str


@dataclass(frozen=True)
class ReviewSuggestionRow:
    """Persisted structured review suggestion row."""

    id: str
    conversation_id: str
    study_chunk_id: str
    source_message_id: str | None
    suggestion_index: int
    candidate_type: str
    simplified: str
    traditional: str
    pinyin: str
    english: str
    rationale: str
    source_excerpt: str
    status: str
    promoted_candidate_card_id: str | None


@dataclass(frozen=True)
class PublicationRecordRow:
    """Persisted publication record row."""

    id: str
    candidate_card_id: str
    putonghua_id: str
    anki_note_id: str | None
    published_at: str | None
    status: str


class ProjectRepository:
    """Project persistence helpers."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def get_or_create_by_name(self, name: str) -> ProjectRecord:
        """Return the named project, creating it if it does not exist."""

        row = self._connection.execute(
            "SELECT id, name FROM projects WHERE name = ?",
            (name,),
        ).fetchone()
        if row is not None:
            return ProjectRecord(id=str(row["id"]), name=str(row["name"]))

        project_id = str(uuid4())
        self._connection.execute(
            "INSERT INTO projects(id, name) VALUES (?, ?)",
            (project_id, name),
        )
        return ProjectRecord(id=project_id, name=name)


class SourceRepository:
    """Source and transcript persistence helpers."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def create_source(
        self,
        record: SourceCreateRecord,
        segments: list[TranscriptSegmentRecord],
    ) -> str:
        """Insert a source and its transcript segments."""

        source_id = str(uuid4())
        self._connection.execute(
            """
            INSERT INTO sources(
                id,
                project_id,
                source_type,
                title,
                content_hash,
                original_path,
                external_id,
                channel_name,
                published_at,
                media_path,
                transcript_source,
                transcript_text,
                metadata_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                source_id,
                record.project_id,
                record.source_type,
                record.title,
                record.content_hash,
                record.original_path,
                record.external_id,
                record.channel_name,
                record.published_at,
                record.media_path,
                record.transcript_source,
                record.transcript_text,
                json.dumps(record.metadata, ensure_ascii=True, sort_keys=True),
            ),
        )

        for segment in segments:
            self._connection.execute(
                """
                INSERT INTO transcript_segments(
                    id,
                    source_id,
                    start_seconds,
                    end_seconds,
                    text,
                    segment_index
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid4()),
                    source_id,
                    segment.start_seconds,
                    segment.end_seconds,
                    segment.text,
                    segment.segment_index,
                ),
            )

        return source_id

    def list_transcript_segments(self, source_id: str) -> list[TranscriptSegmentRow]:
        """Return transcript segments for a source ordered by index."""

        rows = self._connection.execute(
            """
            SELECT
                id,
                source_id,
                start_seconds,
                end_seconds,
                text,
                segment_index
            FROM transcript_segments
            WHERE source_id = ?
            ORDER BY segment_index ASC
            """,
            (source_id,),
        ).fetchall()
        return [
            TranscriptSegmentRow(
                id=str(row["id"]),
                source_id=str(row["source_id"]),
                start_seconds=float(row["start_seconds"]),
                end_seconds=float(row["end_seconds"]),
                text=str(row["text"]),
                segment_index=int(row["segment_index"]),
            )
            for row in rows
        ]

    def get_source_context(self, source_id: str) -> SourceContextRow | None:
        """Return minimal context for one source."""

        row = self._connection.execute(
            """
            SELECT id, project_id, title
            FROM sources
            WHERE id = ?
            """,
            (source_id,),
        ).fetchone()
        if row is None:
            return None
        return SourceContextRow(
            id=str(row["id"]),
            project_id=str(row["project_id"]),
            title=str(row["title"]),
        )


class StudyChunkRepository:
    """Study chunk persistence helpers."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def replace_for_source(
        self,
        source_id: str,
        chunks: list[StudyChunkRecord],
    ) -> list[str]:
        """Replace all stored chunks for a source."""

        self._connection.execute(
            "DELETE FROM study_chunks WHERE source_id = ?",
            (source_id,),
        )
        chunk_ids: list[str] = []
        for chunk in chunks:
            chunk_id = str(uuid4())
            chunk_ids.append(chunk_id)
            self._connection.execute(
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
                    status,
                    last_reviewed_at,
                    notes
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    chunk_id,
                    chunk.source_id,
                    chunk.chunk_index,
                    chunk.start_seconds,
                    chunk.end_seconds,
                    chunk.text,
                    chunk.transcript_segment_count,
                    chunk.char_count,
                    chunk.status,
                    chunk.last_reviewed_at,
                    chunk.notes,
                ),
            )
        return chunk_ids

    def get_next_pending_chunk(self, source_id: str) -> StudyChunkRow | None:
        """Return the next pending chunk for a source."""

        row = self._connection.execute(
            """
            SELECT
                id,
                source_id,
                chunk_index,
                start_seconds,
                end_seconds,
                text,
                transcript_segment_count,
                char_count,
                status,
                last_reviewed_at,
                notes
            FROM study_chunks
            WHERE source_id = ? AND status = 'pending'
            ORDER BY chunk_index ASC
            LIMIT 1
            """,
            (source_id,),
        ).fetchone()
        return _row_to_study_chunk(row)

    def get_chunk(self, chunk_id: str) -> StudyChunkRow | None:
        """Return one chunk by id."""

        row = self._connection.execute(
            """
            SELECT
                id,
                source_id,
                chunk_index,
                start_seconds,
                end_seconds,
                text,
                transcript_segment_count,
                char_count,
                status,
                last_reviewed_at,
                notes
            FROM study_chunks
            WHERE id = ?
            """,
            (chunk_id,),
        ).fetchone()
        return _row_to_study_chunk(row)

    def update_chunk_status(
        self, chunk_id: str, status: str, notes: str | None
    ) -> None:
        """Update status and review metadata for one chunk."""

        self._connection.execute(
            """
            UPDATE study_chunks
            SET
                status = ?,
                notes = ?,
                last_reviewed_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (status, notes, chunk_id),
        )


class CandidateRepository:
    """Candidate card persistence helpers."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def create_candidates(self, records: list[CandidateCardCreateRecord]) -> list[str]:
        """Insert candidate cards and return their ids."""

        candidate_ids: list[str] = []
        for record in records:
            candidate_id = str(uuid4())
            candidate_ids.append(candidate_id)
            self._connection.execute(
                """
                INSERT INTO candidate_cards(
                    id,
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
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    candidate_id,
                    record.project_id,
                    record.source_id,
                    record.study_chunk_id,
                    record.candidate_type,
                    record.status,
                    record.simplified,
                    record.traditional,
                    record.pinyin,
                    record.english,
                    json.dumps(record.provenance, ensure_ascii=True, sort_keys=True),
                ),
            )
        return candidate_ids

    def list_candidates_for_chunk(self, chunk_id: str) -> list[CandidateCardRow]:
        """Return candidate cards linked to one study chunk."""

        rows = self._connection.execute(
            """
            SELECT
                id,
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
            WHERE study_chunk_id = ?
            ORDER BY created_at ASC, id ASC
            """,
            (chunk_id,),
        ).fetchall()
        return [
            CandidateCardRow(
                id=str(row["id"]),
                project_id=str(row["project_id"]),
                source_id=str(row["source_id"]),
                study_chunk_id=(
                    str(row["study_chunk_id"])
                    if row["study_chunk_id"] is not None
                    else None
                ),
                candidate_type=str(row["candidate_type"]),
                status=str(row["status"]),
                simplified=(
                    str(row["simplified"]) if row["simplified"] is not None else None
                ),
                traditional=(
                    str(row["traditional"]) if row["traditional"] is not None else None
                ),
                pinyin=str(row["pinyin"]) if row["pinyin"] is not None else None,
                english=str(row["english"]) if row["english"] is not None else None,
                provenance_json=str(row["provenance_json"]),
            )
            for row in rows
        ]

    def get_candidate(self, candidate_id: str) -> CandidateCardRow | None:
        """Return one candidate card by id."""

        row = self._connection.execute(
            """
            SELECT
                id,
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
            (candidate_id,),
        ).fetchone()
        if row is None:
            return None
        return CandidateCardRow(
            id=str(row["id"]),
            project_id=str(row["project_id"]),
            source_id=str(row["source_id"]),
            study_chunk_id=(
                str(row["study_chunk_id"])
                if row["study_chunk_id"] is not None
                else None
            ),
            candidate_type=str(row["candidate_type"]),
            status=str(row["status"]),
            simplified=(
                str(row["simplified"]) if row["simplified"] is not None else None
            ),
            traditional=(
                str(row["traditional"]) if row["traditional"] is not None else None
            ),
            pinyin=str(row["pinyin"]) if row["pinyin"] is not None else None,
            english=str(row["english"]) if row["english"] is not None else None,
            provenance_json=str(row["provenance_json"]),
        )

    def update_status(self, candidate_id: str, status: str) -> None:
        """Update one candidate card status."""

        self._connection.execute(
            """
            UPDATE candidate_cards
            SET status = ?
            WHERE id = ?
            """,
            (status, candidate_id),
        )


class PublicationRecordRepository:
    """Publication record persistence helpers."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def get_by_candidate_id(self, candidate_id: str) -> PublicationRecordRow | None:
        """Return one publication record for a candidate."""

        row = self._connection.execute(
            """
            SELECT
                id,
                candidate_card_id,
                putonghua_id,
                anki_note_id,
                published_at,
                status
            FROM publication_records
            WHERE candidate_card_id = ?
            """,
            (candidate_id,),
        ).fetchone()
        if row is None:
            return None
        return PublicationRecordRow(
            id=str(row["id"]),
            candidate_card_id=str(row["candidate_card_id"]),
            putonghua_id=str(row["putonghua_id"]),
            anki_note_id=(
                str(row["anki_note_id"]) if row["anki_note_id"] is not None else None
            ),
            published_at=(
                str(row["published_at"]) if row["published_at"] is not None else None
            ),
            status=str(row["status"]),
        )

    def create_publication(
        self,
        *,
        candidate_id: str,
        putonghua_id: str,
        status: str,
    ) -> str:
        """Insert one publication record."""

        publication_id = str(uuid4())
        self._connection.execute(
            """
            INSERT INTO publication_records(
                id,
                candidate_card_id,
                putonghua_id,
                status
            )
            VALUES (?, ?, ?, ?)
            """,
            (publication_id, candidate_id, putonghua_id, status),
        )
        return publication_id

    def mark_published(self, publication_id: str, anki_note_id: int) -> None:
        """Persist Anki note id and published timestamp."""

        self._connection.execute(
            """
            UPDATE publication_records
            SET
                anki_note_id = ?,
                published_at = CURRENT_TIMESTAMP,
                status = 'published'
            WHERE id = ?
            """,
            (str(anki_note_id), publication_id),
        )


class ReviewConversationRepository:
    """Chunk review conversation persistence helpers."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def get_latest_for_chunk(self, chunk_id: str) -> ReviewConversationRow | None:
        """Return the most recent conversation for one chunk."""

        row = self._connection.execute(
            """
            SELECT id, study_chunk_id, provider, model, prompt_version
            FROM review_conversations
            WHERE study_chunk_id = ?
            ORDER BY created_at DESC, id DESC
            LIMIT 1
            """,
            (chunk_id,),
        ).fetchone()
        if row is None:
            return None
        return ReviewConversationRow(
            id=str(row["id"]),
            study_chunk_id=str(row["study_chunk_id"]),
            provider=str(row["provider"]),
            model=str(row["model"]),
            prompt_version=str(row["prompt_version"]),
        )

    def get_conversation(self, conversation_id: str) -> ReviewConversationRow | None:
        """Return one conversation by id."""

        row = self._connection.execute(
            """
            SELECT id, study_chunk_id, provider, model, prompt_version
            FROM review_conversations
            WHERE id = ?
            """,
            (conversation_id,),
        ).fetchone()
        if row is None:
            return None
        return ReviewConversationRow(
            id=str(row["id"]),
            study_chunk_id=str(row["study_chunk_id"]),
            provider=str(row["provider"]),
            model=str(row["model"]),
            prompt_version=str(row["prompt_version"]),
        )

    def create_conversation(
        self,
        *,
        study_chunk_id: str,
        provider: str,
        model: str,
        prompt_version: str,
    ) -> str:
        """Create one review conversation."""

        conversation_id = str(uuid4())
        self._connection.execute(
            """
            INSERT INTO review_conversations(
                id,
                study_chunk_id,
                provider,
                model,
                prompt_version
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (conversation_id, study_chunk_id, provider, model, prompt_version),
        )
        return conversation_id

    def add_message(self, conversation_id: str, role: str, content: str) -> str:
        """Append one message to a conversation."""

        message_id = str(uuid4())
        self._connection.execute(
            """
            INSERT INTO review_messages(id, conversation_id, role, content)
            VALUES (?, ?, ?, ?)
            """,
            (message_id, conversation_id, role, content),
        )
        return message_id

    def list_messages(self, conversation_id: str) -> list[ReviewMessageRow]:
        """Return persisted messages in conversation order."""

        rows = self._connection.execute(
            """
            SELECT id, conversation_id, role, content
            FROM review_messages
            WHERE conversation_id = ?
            ORDER BY created_at ASC, rowid ASC
            """,
            (conversation_id,),
        ).fetchall()
        return [
            ReviewMessageRow(
                id=str(row["id"]),
                conversation_id=str(row["conversation_id"]),
                role=str(row["role"]),
                content=str(row["content"]),
            )
            for row in rows
        ]


class ReviewSuggestionRepository:
    """Structured review suggestion persistence helpers."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def replace_for_message(
        self,
        source_message_id: str,
        suggestions: list[ReviewSuggestionCreateRecord],
    ) -> list[str]:
        """Replace structured suggestions for one assistant message."""

        self._connection.execute(
            "DELETE FROM review_suggestions WHERE source_message_id = ?",
            (source_message_id,),
        )

        suggestion_ids: list[str] = []
        for suggestion in suggestions:
            suggestion_id = str(uuid4())
            suggestion_ids.append(suggestion_id)
            self._connection.execute(
                """
                INSERT INTO review_suggestions(
                    id,
                    conversation_id,
                    study_chunk_id,
                    source_message_id,
                    suggestion_index,
                    candidate_type,
                    simplified,
                    traditional,
                    pinyin,
                    english,
                    rationale,
                    source_excerpt,
                    status,
                    promoted_candidate_card_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'suggested', NULL)
                """,
                (
                    suggestion_id,
                    suggestion.conversation_id,
                    suggestion.study_chunk_id,
                    suggestion.source_message_id,
                    suggestion.suggestion_index,
                    suggestion.candidate_type,
                    suggestion.simplified,
                    suggestion.traditional,
                    suggestion.pinyin,
                    suggestion.english,
                    suggestion.rationale,
                    suggestion.source_excerpt,
                ),
            )
        return suggestion_ids

    def list_for_conversation(self, conversation_id: str) -> list[ReviewSuggestionRow]:
        """Return structured suggestions for one conversation."""

        rows = self._connection.execute(
            """
            SELECT
                id,
                conversation_id,
                study_chunk_id,
                source_message_id,
                suggestion_index,
                candidate_type,
                simplified,
                traditional,
                pinyin,
                english,
                rationale,
                source_excerpt,
                status,
                promoted_candidate_card_id
            FROM review_suggestions
            WHERE conversation_id = ?
            ORDER BY suggestion_index ASC, created_at ASC, id ASC
            """,
            (conversation_id,),
        ).fetchall()
        return [
            ReviewSuggestionRow(
                id=str(row["id"]),
                conversation_id=str(row["conversation_id"]),
                study_chunk_id=str(row["study_chunk_id"]),
                source_message_id=(
                    str(row["source_message_id"])
                    if row["source_message_id"] is not None
                    else None
                ),
                suggestion_index=int(row["suggestion_index"]),
                candidate_type=str(row["candidate_type"]),
                simplified=str(row["simplified"]),
                traditional=str(row["traditional"]),
                pinyin=str(row["pinyin"]),
                english=str(row["english"]),
                rationale=str(row["rationale"]),
                source_excerpt=str(row["source_excerpt"]),
                status=str(row["status"]),
                promoted_candidate_card_id=(
                    str(row["promoted_candidate_card_id"])
                    if row["promoted_candidate_card_id"] is not None
                    else None
                ),
            )
            for row in rows
        ]

    def get_suggestion(self, suggestion_id: str) -> ReviewSuggestionRow | None:
        """Return one structured suggestion by id."""

        row = self._connection.execute(
            """
            SELECT
                id,
                conversation_id,
                study_chunk_id,
                source_message_id,
                suggestion_index,
                candidate_type,
                simplified,
                traditional,
                pinyin,
                english,
                rationale,
                source_excerpt,
                status,
                promoted_candidate_card_id
            FROM review_suggestions
            WHERE id = ?
            """,
            (suggestion_id,),
        ).fetchone()
        if row is None:
            return None
        return ReviewSuggestionRow(
            id=str(row["id"]),
            conversation_id=str(row["conversation_id"]),
            study_chunk_id=str(row["study_chunk_id"]),
            source_message_id=(
                str(row["source_message_id"])
                if row["source_message_id"] is not None
                else None
            ),
            suggestion_index=int(row["suggestion_index"]),
            candidate_type=str(row["candidate_type"]),
            simplified=str(row["simplified"]),
            traditional=str(row["traditional"]),
            pinyin=str(row["pinyin"]),
            english=str(row["english"]),
            rationale=str(row["rationale"]),
            source_excerpt=str(row["source_excerpt"]),
            status=str(row["status"]),
            promoted_candidate_card_id=(
                str(row["promoted_candidate_card_id"])
                if row["promoted_candidate_card_id"] is not None
                else None
            ),
        )

    def mark_promoted(self, suggestion_id: str, candidate_card_id: str) -> None:
        """Mark one suggestion as promoted and link the durable candidate."""

        self._connection.execute(
            """
            UPDATE review_suggestions
            SET status = 'promoted', promoted_candidate_card_id = ?
            WHERE id = ?
            """,
            (candidate_card_id, suggestion_id),
        )


def _row_to_study_chunk(row: sqlite3.Row | None) -> StudyChunkRow | None:
    """Convert a sqlite row into a typed chunk row."""

    if row is None:
        return None
    return StudyChunkRow(
        id=str(row["id"]),
        source_id=str(row["source_id"]),
        chunk_index=int(row["chunk_index"]),
        start_seconds=float(row["start_seconds"]),
        end_seconds=float(row["end_seconds"]),
        text=str(row["text"]),
        transcript_segment_count=int(row["transcript_segment_count"]),
        char_count=int(row["char_count"]),
        status=str(row["status"]),
        last_reviewed_at=(
            str(row["last_reviewed_at"])
            if row["last_reviewed_at"] is not None
            else None
        ),
        notes=str(row["notes"]) if row["notes"] is not None else None,
    )
