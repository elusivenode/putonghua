"""Views for resumable source transcription."""

from dataclasses import dataclass


@dataclass(frozen=True)
class TranscriptionProgress:
    """Persisted transcription progress for one source."""

    source_id: str
    total_windows: int
    completed_windows: int
    failed_windows: int
    next_start_seconds: float | None
    next_end_seconds: float | None


@dataclass(frozen=True)
class TranscribedWindowResult:
    """One successfully persisted transcription window."""

    source_id: str
    window_index: int
    start_seconds: float
    end_seconds: float
    study_chunk_id: str
    progress: TranscriptionProgress
