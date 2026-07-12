"""OpenAI transcription provider."""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import httpx

from putonghua.models.source import Transcript, TranscriptSegment


@dataclass(frozen=True)
class OpenAITranscriptionConfig:
    """OpenAI transcription request settings."""

    api_key: str
    model: str
    language: str
    prompt: str | None
    timeout_seconds: float
    max_upload_bytes: int
    transcription_bitrate_kbps: int
    chunk_duration_seconds: int


class OpenAITranscriptionProvider:
    """Thin wrapper over the OpenAI speech-to-text API."""

    def __init__(self, config: OpenAITranscriptionConfig) -> None:
        self._config = config

    def transcribe(self, audio_path: Path) -> Transcript:
        """Transcribe an audio file with timestamped segments."""

        prepared_audio_paths = prepare_audio_paths_for_transcription(
            config=self._config,
            audio_path=audio_path,
        )
        transcripts: list[tuple[Transcript, float]] = []
        elapsed_seconds = 0.0
        for prepared_path in prepared_audio_paths:
            transcript = self._transcribe_file(prepared_path)
            transcripts.append((transcript, elapsed_seconds))
            elapsed_seconds += _probe_duration_seconds(prepared_path)

        if len(transcripts) == 1:
            return transcripts[0][0]

        merged_segments: list[TranscriptSegment] = []
        merged_texts: list[str] = []
        for transcript, offset in transcripts:
            merged_texts.append(transcript.text)
            for segment in transcript.segments:
                merged_segments.append(
                    TranscriptSegment(
                        start_seconds=segment.start_seconds + offset,
                        end_seconds=segment.end_seconds + offset,
                        text=segment.text,
                    )
                )

        return Transcript(
            source_kind="openai_transcription",
            text="\n".join(text for text in merged_texts if text.strip()),
            segments=merged_segments,
        )

    def _transcribe_file(self, audio_path: Path) -> Transcript:
        """Transcribe a single prepared file."""

        with audio_path.open("rb") as handle:
            files = {"file": (audio_path.name, handle, "application/octet-stream")}
            data: dict[str, object] = {
                "model": self._config.model,
                "response_format": "verbose_json",
            }
            if self._config.model == "whisper-1":
                data["timestamp_granularities[]"] = "segment"
            if self._config.language:
                data["language"] = self._config.language
            if self._config.prompt:
                data["prompt"] = self._config.prompt

            with httpx.Client(timeout=self._config.timeout_seconds) as client:
                try:
                    response = client.post(
                        "https://api.openai.com/v1/audio/transcriptions",
                        headers={"Authorization": f"Bearer {self._config.api_key}"},
                        files=files,
                        data=data,
                    )
                    response.raise_for_status()
                except httpx.ReadTimeout as exc:
                    message = (
                        "OpenAI transcription timed out while waiting for the "
                        "API response."
                    )
                    raise ValueError(message) from exc

        payload = cast(dict[str, Any], response.json())
        raw_text = payload.get("text")
        if not isinstance(raw_text, str):
            message = "OpenAI transcription did not include transcript text."
            raise ValueError(message)

        raw_segments = payload.get("segments")
        segments: list[TranscriptSegment] = []
        if isinstance(raw_segments, list):
            for item in cast(list[object], raw_segments):
                if not isinstance(item, dict):
                    continue
                segment_item = cast(dict[str, object], item)
                start = segment_item.get("start")
                end = segment_item.get("end")
                text = segment_item.get("text")
                if (
                    isinstance(start, int | float)
                    and isinstance(end, int | float)
                    and isinstance(text, str)
                ):
                    segments.append(
                        TranscriptSegment(
                            start_seconds=float(start),
                            end_seconds=float(end),
                            text=text.strip(),
                        )
                    )

        if not segments:
            segments = [
                TranscriptSegment(
                    start_seconds=0.0,
                    end_seconds=0.0,
                    text=raw_text.strip(),
                )
            ]

        return Transcript(
            source_kind="openai_transcription",
            text=raw_text.strip(),
            segments=segments,
        )


def prepare_audio_paths_for_transcription(
    *,
    config: OpenAITranscriptionConfig,
    audio_path: Path,
) -> list[Path]:
    """Prepare transcription-friendly audio files within upload limits."""

    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        if audio_path.stat().st_size > config.max_upload_bytes:
            message = (
                "Audio exceeds the OpenAI upload limit and ffmpeg/ffprobe "
                "are unavailable for transcoding or chunking."
            )
            raise ValueError(message)
        return [audio_path]

    if audio_path.stat().st_size <= config.max_upload_bytes:
        return [audio_path]

    transcription_dir = audio_path.parent / "transcription"
    transcription_dir.mkdir(parents=True, exist_ok=True)
    normalized_path = transcription_dir / f"{audio_path.stem}.transcription.mp3"
    _transcode_audio(
        source_path=audio_path,
        output_path=normalized_path,
        bitrate_kbps=config.transcription_bitrate_kbps,
    )

    if normalized_path.stat().st_size <= config.max_upload_bytes:
        return [normalized_path]

    chunk_dir = transcription_dir / "chunks"
    chunk_dir.mkdir(parents=True, exist_ok=True)
    for existing in chunk_dir.glob("chunk_*.mp3"):
        existing.unlink()

    chunk_template = chunk_dir / "chunk_%03d.mp3"
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(normalized_path),
            "-f",
            "segment",
            "-segment_time",
            str(config.chunk_duration_seconds),
            "-c",
            "copy",
            str(chunk_template),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    chunk_paths = sorted(chunk_dir.glob("chunk_*.mp3"))
    if not chunk_paths:
        message = "ffmpeg did not produce transcription chunks."
        raise ValueError(message)

    oversized = [
        path.name
        for path in chunk_paths
        if path.stat().st_size > config.max_upload_bytes
    ]
    if oversized:
        message = (
            "One or more audio chunks still exceed the OpenAI upload limit: "
            + ", ".join(oversized)
        )
        raise ValueError(message)

    return chunk_paths


def _transcode_audio(
    *,
    source_path: Path,
    output_path: Path,
    bitrate_kbps: int,
) -> None:
    """Create a low-bitrate mono MP3 for transcription."""

    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(source_path),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-b:a",
            f"{bitrate_kbps}k",
            str(output_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )


def _probe_duration_seconds(audio_path: Path) -> float:
    """Return media duration in seconds using ffprobe."""

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
