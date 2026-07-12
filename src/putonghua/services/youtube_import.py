"""YouTube import workflow."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, cast

from putonghua.database.connection import connect
from putonghua.database.migrations import migrate_database
from putonghua.database.repositories import (
    ProjectRepository,
    SourceCreateRecord,
    SourceRepository,
    TranscriptSegmentRecord,
)
from putonghua.models.source import Transcript, TranscriptSegment, YouTubeImportResult

YOUTUBE_SUBTITLE_LANGS = "zh.*,zh-Hans,zh-Hant,zh-CN,zh-TW,zh"


@dataclass(frozen=True)
class YouTubeVideoMetadata:
    """Downloaded metadata for one YouTube video."""

    video_id: str
    title: str
    channel_name: str | None
    upload_date: str | None
    webpage_url: str
    raw_metadata: dict[str, Any]


class DownloaderProtocol(Protocol):
    """Abstract media downloader."""

    def fetch_metadata(self, url: str) -> YouTubeVideoMetadata:
        """Fetch metadata without downloading the media."""
        ...

    def download_audio(self, metadata: YouTubeVideoMetadata, output_dir: Path) -> Path:
        """Download the audio track."""
        ...

    def download_subtitles(
        self,
        metadata: YouTubeVideoMetadata,
        output_dir: Path,
    ) -> Path | None:
        """Download Chinese subtitles if available."""
        ...


class TranscriberProtocol(Protocol):
    """Abstract transcription provider."""

    def transcribe(self, audio_path: Path) -> Transcript:
        """Transcribe an audio file."""
        ...


class YtDlpDownloader:
    """Small wrapper around yt-dlp."""

    def fetch_metadata(self, url: str) -> YouTubeVideoMetadata:
        """Fetch metadata for a video."""

        result = subprocess.run(
            ["yt-dlp", "--dump-single-json", "--no-playlist", "--no-download", url],
            check=True,
            capture_output=True,
            text=True,
        )
        payload = cast(dict[str, Any], json.loads(result.stdout))
        video_id = payload.get("id")
        title = payload.get("title")
        webpage_url = payload.get("webpage_url") or url
        if not isinstance(video_id, str) or not isinstance(title, str):
            message = "yt-dlp did not return stable id/title metadata."
            raise ValueError(message)

        channel_name = payload.get("channel")
        upload_date = payload.get("upload_date")
        return YouTubeVideoMetadata(
            video_id=video_id,
            title=title,
            channel_name=channel_name if isinstance(channel_name, str) else None,
            upload_date=upload_date if isinstance(upload_date, str) else None,
            webpage_url=webpage_url if isinstance(webpage_url, str) else url,
            raw_metadata=payload,
        )

    def download_audio(self, metadata: YouTubeVideoMetadata, output_dir: Path) -> Path:
        """Download the best available audio stream."""

        output_dir.mkdir(parents=True, exist_ok=True)
        template = str(output_dir / f"{metadata.video_id}.%(ext)s")
        subprocess.run(
            [
                "yt-dlp",
                "--no-playlist",
                "-f",
                "bestaudio/best",
                "-o",
                template,
                metadata.webpage_url,
            ],
            check=True,
            capture_output=True,
            text=True,
        )

        audio_files = sorted(
            path
            for path in output_dir.glob(f"{metadata.video_id}.*")
            if path.is_file() and path.suffix not in {".json", ".vtt", ".srt"}
        )
        if not audio_files:
            message = "yt-dlp completed without producing an audio file."
            raise ValueError(message)
        return audio_files[0]

    def download_subtitles(
        self,
        metadata: YouTubeVideoMetadata,
        output_dir: Path,
    ) -> Path | None:
        """Download Chinese subtitles when available."""

        output_dir.mkdir(parents=True, exist_ok=True)
        template = str(output_dir / f"{metadata.video_id}.%(ext)s")
        subprocess.run(
            [
                "yt-dlp",
                "--no-playlist",
                "--skip-download",
                "--write-subs",
                "--write-auto-subs",
                "--sub-langs",
                YOUTUBE_SUBTITLE_LANGS,
                "--sub-format",
                "vtt/best",
                "-o",
                template,
                metadata.webpage_url,
            ],
            check=True,
            capture_output=True,
            text=True,
        )

        candidates = sorted(output_dir.glob(f"{metadata.video_id}*.vtt"))
        if not candidates:
            return None
        return candidates[0]


class YouTubeImportService:
    """Import one YouTube episode into local project state."""

    def __init__(
        self,
        *,
        database_path: Path,
        data_dir: Path,
        downloader: DownloaderProtocol,
        transcriber: TranscriberProtocol | None,
    ) -> None:
        self._database_path = database_path
        self._data_dir = data_dir
        self._downloader = downloader
        self._transcriber = transcriber

    def import_url(self, *, project_name: str, url: str) -> YouTubeImportResult:
        """Import a single YouTube URL and persist its transcript."""

        migrate_database(self._database_path)
        metadata = self._downloader.fetch_metadata(url)
        source_dir = self._data_dir / "youtube" / metadata.video_id
        source_dir.mkdir(parents=True, exist_ok=True)

        audio_path = self._downloader.download_audio(metadata, source_dir)
        subtitle_path = self._downloader.download_subtitles(metadata, source_dir)

        transcript = (
            parse_vtt_transcript(subtitle_path)
            if subtitle_path is not None
            else self._transcribe_audio(audio_path)
        )

        if subtitle_path is None and transcript.source_kind == "openai_transcription":
            transcript_source = "openai_transcription"
        elif subtitle_path is not None:
            transcript_source = "subtitles"
        else:
            transcript_source = transcript.source_kind

        content_hash = _hash_file(audio_path)
        with connect(self._database_path) as connection:
            projects = ProjectRepository(connection)
            sources = SourceRepository(connection)
            project = projects.get_or_create_by_name(project_name)
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
                    transcript_source=transcript_source,
                    transcript_text=transcript.text,
                    metadata=metadata.raw_metadata,
                ),
                [
                    TranscriptSegmentRecord(
                        start_seconds=segment.start_seconds,
                        end_seconds=segment.end_seconds,
                        text=segment.text,
                        segment_index=index,
                    )
                    for index, segment in enumerate(transcript.segments)
                ],
            )

        return YouTubeImportResult(
            source_id=source_id,
            project_id=project.id,
            project_name=project.name,
            title=metadata.title,
            channel_name=metadata.channel_name,
            media_path=audio_path,
            transcript_source=transcript_source,
        )

    def _transcribe_audio(self, audio_path: Path) -> Transcript:
        """Transcribe audio when no subtitles are available."""

        if self._transcriber is None:
            message = (
                "No subtitles were available and no transcription provider "
                "is configured."
            )
            raise ValueError(message)
        return self._transcriber.transcribe(audio_path)


def _hash_file(path: Path) -> str:
    """Return the SHA-256 for a file."""

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_vtt_transcript(path: Path) -> Transcript:
    """Parse a simple VTT transcript into segments."""

    raw_lines = path.read_text(encoding="utf-8").splitlines()
    segments: list[TranscriptSegment] = []
    i = 0
    while i < len(raw_lines):
        line = raw_lines[i].strip()
        if "-->" not in line:
            i += 1
            continue

        start_text, end_text = [part.strip() for part in line.split("-->", maxsplit=1)]
        start_seconds = _parse_vtt_timestamp(start_text)
        end_seconds = _parse_vtt_timestamp(end_text.split(" ", maxsplit=1)[0])
        i += 1

        text_lines: list[str] = []
        while i < len(raw_lines) and raw_lines[i].strip():
            cleaned = re.sub(r"<[^>]+>", "", raw_lines[i]).strip()
            if cleaned:
                text_lines.append(cleaned)
            i += 1
        merged_text = " ".join(text_lines).strip()
        if merged_text:
            segments.append(
                TranscriptSegment(
                    start_seconds=start_seconds,
                    end_seconds=end_seconds,
                    text=merged_text,
                )
            )
        i += 1

    if not segments:
        message = f"No transcript segments could be parsed from subtitle file: {path}"
        raise ValueError(message)

    transcript_text = "\n".join(segment.text for segment in segments)
    return Transcript(
        source_kind="subtitles",
        text=transcript_text,
        segments=segments,
    )


def _parse_vtt_timestamp(value: str) -> float:
    """Parse a VTT timestamp into seconds."""

    parts = value.split(":")
    if len(parts) == 3:
        hours_text, minutes_text, seconds_text = parts
    elif len(parts) == 2:
        hours_text = "0"
        minutes_text, seconds_text = parts
    else:
        message = f"Unsupported VTT timestamp: {value}"
        raise ValueError(message)

    return (
        int(hours_text) * 3600
        + int(minutes_text) * 60
        + float(seconds_text.replace(",", "."))
    )
