"""Study chunk models."""

from dataclasses import dataclass


@dataclass(frozen=True)
class StudyChunkBuildResult:
    """Result of building study chunks for a source."""

    source_id: str
    chunk_count: int
    chunk_ids: list[str]


@dataclass(frozen=True)
class StudyChunkView:
    """Chunk view for work-queue operations."""

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
class StudyChunkStatusResult:
    """Result of updating chunk status."""

    chunk_id: str
    status: str
