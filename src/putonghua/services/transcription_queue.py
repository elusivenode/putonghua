"""Resumable, fixed-duration OpenAI transcription workflow."""

from __future__ import annotations

import hashlib
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from putonghua.database.connection import connect
from putonghua.database.migrations import migrate_database
from putonghua.database.repositories import (
    SourceCreateRecord,
    SourceRepository,
    StudyChunkRecord,
    StudyChunkRepository,
    TranscriptionWindowRepository,
    TranscriptSegmentRecord,
)
from putonghua.models.source import Transcript
from putonghua.models.transcription import (
    TranscribedWindowResult,
    TranscriptionProgress,
)
from putonghua.services.youtube_import import DownloaderProtocol


class WindowTranscriber(Protocol):
    def transcribe(self, audio_path: Path) -> Transcript: ...


@dataclass(frozen=True)
class PreparedSource:
    source_id: str
    total_windows: int
    duration_seconds: float


class TranscriptionQueueService:
    """Prepare and advance a source one persisted audio window at a time."""

    def __init__(
        self,
        *,
        database_path: Path,
        data_dir: Path,
        downloader: DownloaderProtocol,
        transcriber: WindowTranscriber,
        model: str,
        prompt: str | None,
    ) -> None:
        self._database_path = database_path
        self._data_dir = data_dir
        self._downloader = downloader
        self._transcriber = transcriber
        self._model = model
        self._prompt = prompt

    def prepare(
        self, *, project_name: str, url: str, window_seconds: int = 60
    ) -> PreparedSource:
        if window_seconds != 60:
            raise ValueError("Only 60-second transcription windows are supported.")
        migrate_database(self._database_path)
        metadata = self._downloader.fetch_metadata(url)
        source_dir = self._data_dir / "youtube" / metadata.video_id
        audio_path = self._downloader.download_audio(metadata, source_dir)
        content_hash = _hash_file(audio_path)
        duration = _probe_duration_seconds(audio_path)
        with connect(self._database_path) as connection:
            sources = SourceRepository(connection)
            existing = sources.get_source_by_content_hash(content_hash)
            if existing is None:
                from putonghua.database.repositories import ProjectRepository

                project = ProjectRepository(connection).get_or_create_by_name(
                    project_name
                )
                source_id = sources.create_source(
                    SourceCreateRecord(
                        project_id=project.id,
                        source_type="youtube_audio",
                        title=metadata.title,
                        content_hash=content_hash,
                        original_path=metadata.webpage_url,
                        external_id=metadata.video_id,
                        channel_name=metadata.channel_name,
                        published_at=metadata.upload_date,
                        media_path=str(audio_path),
                        transcript_source="openai_transcription",
                        transcript_text=None,
                        metadata=metadata.raw_metadata,
                    ),
                    [],
                )
            else:
                source_id = existing.id
            windows = TranscriptionWindowRepository(connection)
            windows.create_for_source(source_id, duration, window_seconds)
            total = windows.count_for_source(source_id)
        return PreparedSource(
            source_id=source_id, total_windows=total, duration_seconds=duration
        )

    def status(self, source_id: str) -> TranscriptionProgress:
        migrate_database(self._database_path)
        with connect(self._database_path) as connection:
            return TranscriptionWindowRepository(connection).progress(source_id)

    def transcribe_next(self, source_id: str) -> TranscribedWindowResult | None:
        migrate_database(self._database_path)
        with connect(self._database_path) as connection:
            sources = SourceRepository(connection)
            source = sources.get_source_details(source_id)
            if source is None or source.media_path is None:
                raise ValueError(f"No local audio source found for {source_id}")
            windows = TranscriptionWindowRepository(connection)
            window = windows.next_pending(source_id)
            if window is None:
                return None
            windows.mark_in_progress(window.id)
            audio_path = Path(source.media_path)

        try:
            slice_path = _make_window_slice(
                audio_path, window.start_seconds, window.end_seconds
            )
            transcript = self._transcriber.transcribe(slice_path)
        except Exception as exc:
            with connect(self._database_path) as connection:
                TranscriptionWindowRepository(connection).mark_failed(
                    window.id, str(exc)
                )
            raise

        offset_segments = [
            TranscriptSegmentRecord(
                start_seconds=segment.start_seconds + window.start_seconds,
                end_seconds=segment.end_seconds + window.start_seconds,
                text=segment.text,
                segment_index=window.window_index * 10_000 + index,
            )
            for index, segment in enumerate(transcript.segments)
            if segment.text.strip()
        ]
        text = " ".join(
            segment.text.strip()
            for segment in transcript.segments
            if segment.text.strip()
        )
        if not text:
            text = transcript.text.strip()
        with connect(self._database_path) as connection:
            sources = SourceRepository(connection)
            chunks = StudyChunkRepository(connection)
            windows = TranscriptionWindowRepository(connection)
            sources.replace_transcript_segments_for_window(
                source_id, window.window_index, offset_segments
            )
            sources.refresh_transcript_text(source_id)
            chunk_id = chunks.upsert(
                StudyChunkRecord(
                    source_id=source_id,
                    chunk_index=window.window_index,
                    start_seconds=window.start_seconds,
                    end_seconds=window.end_seconds,
                    text=text,
                    transcript_segment_count=len(offset_segments),
                    char_count=len(text),
                )
            )
            windows.mark_completed(window.id, text, self._model, self._prompt)
            progress = windows.progress(source_id)
        return TranscribedWindowResult(
            source_id,
            window.window_index,
            window.start_seconds,
            window.end_seconds,
            chunk_id,
            progress,
        )


def _make_window_slice(
    audio_path: Path, start_seconds: float, end_seconds: float
) -> Path:
    output_dir = audio_path.parent / "transcription" / "windows"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{int(start_seconds):06d}-{int(end_seconds):06d}.mp3"
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-ss",
            str(start_seconds),
            "-i",
            str(audio_path),
            "-t",
            str(end_seconds - start_seconds),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-b:a",
            "64k",
            str(output_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return output_path


def _probe_duration_seconds(audio_path: Path) -> float:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(audio_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return float(result.stdout.strip())


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for data in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(data)
    return digest.hexdigest()
