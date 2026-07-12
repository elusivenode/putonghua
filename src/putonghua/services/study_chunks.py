"""Study chunk construction from transcript segments."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from putonghua.database.connection import connect
from putonghua.database.migrations import migrate_database
from putonghua.database.repositories import (
    SourceRepository,
    StudyChunkRecord,
    StudyChunkRepository,
    StudyChunkRow,
    TranscriptSegmentRow,
)
from putonghua.models.chunks import (
    StudyChunkBuildResult,
    StudyChunkStatusResult,
    StudyChunkView,
)

SENTENCE_ENDINGS = ("。", "？", "！", ".", "?", "!")


@dataclass(frozen=True)
class StudyChunkBuildConfig:
    """Chunk construction thresholds."""

    max_duration_seconds: float = 90.0
    max_char_count: int = 700
    min_duration_seconds: float = 25.0
    min_char_count: int = 140


class StudyChunkService:
    """Build transcript-derived study chunks."""

    def __init__(self, *, database_path: Path) -> None:
        self._database_path = database_path

    def build_for_source(
        self,
        source_id: str,
        config: StudyChunkBuildConfig | None = None,
    ) -> StudyChunkBuildResult:
        """Build and persist study chunks for one source."""

        chunk_config = config or StudyChunkBuildConfig()
        migrate_database(self._database_path)

        with connect(self._database_path) as connection:
            source_repository = SourceRepository(connection)
            chunk_repository = StudyChunkRepository(connection)
            segments = source_repository.list_transcript_segments(source_id)
            if not segments:
                message = f"No transcript segments found for source {source_id}"
                raise ValueError(message)

            chunks = _build_chunks(source_id, segments, chunk_config)
            chunk_ids = chunk_repository.replace_for_source(source_id, chunks)

        return StudyChunkBuildResult(
            source_id=source_id,
            chunk_count=len(chunks),
            chunk_ids=chunk_ids,
        )

    def get_next_pending_chunk(self, source_id: str) -> StudyChunkView | None:
        """Return the next pending chunk for a source."""

        migrate_database(self._database_path)
        with connect(self._database_path) as connection:
            repository = StudyChunkRepository(connection)
            row = repository.get_next_pending_chunk(source_id)
        return _view_from_row(row)

    def get_chunk(self, chunk_id: str) -> StudyChunkView | None:
        """Return one chunk by id."""

        migrate_database(self._database_path)
        with connect(self._database_path) as connection:
            repository = StudyChunkRepository(connection)
            row = repository.get_chunk(chunk_id)
        return _view_from_row(row)

    def update_chunk_status(
        self,
        chunk_id: str,
        status: str,
        notes: str | None = None,
    ) -> StudyChunkStatusResult:
        """Update one chunk status."""

        if status not in {"pending", "in_review", "completed", "skipped"}:
            message = f"Unsupported chunk status: {status}"
            raise ValueError(message)

        migrate_database(self._database_path)
        with connect(self._database_path) as connection:
            repository = StudyChunkRepository(connection)
            existing = repository.get_chunk(chunk_id)
            if existing is None:
                message = f"No study chunk found for id {chunk_id}"
                raise ValueError(message)
            repository.update_chunk_status(chunk_id, status, notes)

        return StudyChunkStatusResult(chunk_id=chunk_id, status=status)


def _build_chunks(
    source_id: str,
    segments: list[TranscriptSegmentRow],
    config: StudyChunkBuildConfig,
) -> list[StudyChunkRecord]:
    """Group transcript segments into pedagogical chunks."""

    chunks: list[StudyChunkRecord] = []
    current: list[TranscriptSegmentRow] = []

    for segment in segments:
        current.append(segment)
        if _should_close_chunk(current, config):
            chunks.append(_make_chunk_record(source_id, len(chunks), current))
            current = []

    if current:
        if chunks and _can_merge_tail(chunks[-1], current, config):
            chunks[-1] = _merge_chunk_with_tail(chunks[-1], current)
        else:
            chunks.append(_make_chunk_record(source_id, len(chunks), current))

    return chunks


def _should_close_chunk(
    segments: list[TranscriptSegmentRow],
    config: StudyChunkBuildConfig,
) -> bool:
    """Return whether the current chunk candidate should be closed."""

    duration = segments[-1].end_seconds - segments[0].start_seconds
    char_count = sum(len(segment.text) for segment in segments)
    latest_text = segments[-1].text.strip()
    at_sentence_boundary = latest_text.endswith(SENTENCE_ENDINGS)

    if duration >= config.max_duration_seconds or char_count >= config.max_char_count:
        return True
    if (
        duration >= config.min_duration_seconds
        and char_count >= config.min_char_count
        and at_sentence_boundary
    ):
        return True
    return False


def _make_chunk_record(
    source_id: str,
    chunk_index: int,
    segments: list[TranscriptSegmentRow],
) -> StudyChunkRecord:
    """Construct a persisted chunk record from transcript segments."""

    text = " ".join(
        segment.text.strip() for segment in segments if segment.text.strip()
    )
    return StudyChunkRecord(
        source_id=source_id,
        chunk_index=chunk_index,
        start_seconds=segments[0].start_seconds,
        end_seconds=segments[-1].end_seconds,
        text=text,
        transcript_segment_count=len(segments),
        char_count=len(text),
    )


def _can_merge_tail(
    chunk: StudyChunkRecord,
    tail_segments: list[TranscriptSegmentRow],
    config: StudyChunkBuildConfig,
) -> bool:
    """Return whether a short final tail should merge into the previous chunk."""

    tail_text = " ".join(
        segment.text.strip() for segment in tail_segments if segment.text.strip()
    )
    tail_duration = tail_segments[-1].end_seconds - tail_segments[0].start_seconds
    merged_duration = tail_segments[-1].end_seconds - chunk.start_seconds
    merged_char_count = (
        len(chunk.text) + (1 if chunk.text and tail_text else 0) + len(tail_text)
    )
    return (
        (
            tail_duration < config.min_duration_seconds
            or len(tail_text) < config.min_char_count
        )
        and merged_duration <= config.max_duration_seconds * 1.5
        and merged_char_count <= config.max_char_count * 1.5
    )


def _merge_chunk_with_tail(
    chunk: StudyChunkRecord,
    tail_segments: list[TranscriptSegmentRow],
) -> StudyChunkRecord:
    """Merge a short tail into the previous chunk."""

    tail_text = " ".join(
        segment.text.strip() for segment in tail_segments if segment.text.strip()
    )
    merged_text = f"{chunk.text} {tail_text}".strip()
    return StudyChunkRecord(
        source_id=chunk.source_id,
        chunk_index=chunk.chunk_index,
        start_seconds=chunk.start_seconds,
        end_seconds=tail_segments[-1].end_seconds,
        text=merged_text,
        transcript_segment_count=chunk.transcript_segment_count + len(tail_segments),
        char_count=len(merged_text),
    )


def _view_from_row(row: StudyChunkRow | None) -> StudyChunkView | None:
    """Convert a persisted chunk row into a public view."""

    if row is None:
        return None
    return StudyChunkView(
        id=row.id,
        source_id=row.source_id,
        chunk_index=row.chunk_index,
        start_seconds=row.start_seconds,
        end_seconds=row.end_seconds,
        text=row.text,
        transcript_segment_count=row.transcript_segment_count,
        char_count=row.char_count,
        status=row.status,
        last_reviewed_at=row.last_reviewed_at,
        notes=row.notes,
    )
