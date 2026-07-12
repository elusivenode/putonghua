"""Source domain models."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class TranscriptSegment:
    """Transcript segment with timing."""

    start_seconds: float
    end_seconds: float
    text: str


@dataclass(frozen=True)
class Transcript:
    """Transcript bundle with provenance."""

    source_kind: str
    text: str
    segments: list[TranscriptSegment]


@dataclass(frozen=True)
class YouTubeImportResult:
    """Result of a YouTube import."""

    source_id: str
    project_id: str
    project_name: str
    title: str
    channel_name: str | None
    media_path: Path
    transcript_source: str
