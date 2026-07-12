from pathlib import Path

from putonghua.models.source import Transcript, TranscriptSegment
from putonghua.services.youtube_import import (
    YouTubeImportService,
    YouTubeVideoMetadata,
    parse_vtt_transcript,
)


class _FakeDownloader:
    def __init__(self, *, subtitle_path: Path | None, audio_path: Path) -> None:
        self.subtitle_path = subtitle_path
        self.audio_path = audio_path

    def fetch_metadata(self, url: str) -> YouTubeVideoMetadata:
        return YouTubeVideoMetadata(
            video_id="abc123",
            title="Episode 23",
            channel_name="Tea with Mona",
            upload_date="20260711",
            webpage_url=url,
            raw_metadata={"id": "abc123", "title": "Episode 23"},
        )

    def download_audio(self, metadata: YouTubeVideoMetadata, output_dir: Path) -> Path:
        del metadata, output_dir
        return self.audio_path

    def download_subtitles(
        self,
        metadata: YouTubeVideoMetadata,
        output_dir: Path,
    ) -> Path | None:
        del metadata, output_dir
        return self.subtitle_path


class _FakeTranscriber:
    def transcribe(self, audio_path: Path) -> Transcript:
        del audio_path
        return Transcript(
            source_kind="openai_transcription",
            text="fallback transcript",
            segments=[
                TranscriptSegment(0.0, 3.0, "fallback transcript"),
            ],
        )


def test_parse_vtt_transcript_returns_segments(tmp_path: Path) -> None:
    subtitle_path = tmp_path / "episode.vtt"
    subtitle_path.write_text(
        "\n".join(
            [
                "WEBVTT",
                "",
                "00:00:00.000 --> 00:00:01.500",
                "你好",
                "",
                "00:00:01.500 --> 00:00:03.000",
                "我們開始吧",
                "",
            ]
        ),
        encoding="utf-8",
    )

    transcript = parse_vtt_transcript(subtitle_path)

    assert transcript.source_kind == "subtitles"
    assert len(transcript.segments) == 2
    assert transcript.segments[0].text == "你好"


def test_youtube_import_prefers_subtitles(tmp_path: Path) -> None:
    audio_path = tmp_path / "episode.webm"
    audio_path.write_bytes(b"audio")
    subtitle_path = tmp_path / "episode.vtt"
    subtitle_path.write_text(
        "\n".join(
            [
                "WEBVTT",
                "",
                "00:00:00.000 --> 00:00:01.000",
                "你好",
                "",
            ]
        ),
        encoding="utf-8",
    )

    service = YouTubeImportService(
        database_path=tmp_path / "putonghua.db",
        data_dir=tmp_path / "data",
        downloader=_FakeDownloader(subtitle_path=subtitle_path, audio_path=audio_path),
        transcriber=_FakeTranscriber(),
    )

    result = service.import_url(
        project_name="Mandarin Podcast",
        url="https://youtube.com/watch?v=abc123",
    )

    assert result.transcript_source == "subtitles"


def test_youtube_import_falls_back_to_transcriber(tmp_path: Path) -> None:
    audio_path = tmp_path / "episode.webm"
    audio_path.write_bytes(b"audio")

    service = YouTubeImportService(
        database_path=tmp_path / "putonghua.db",
        data_dir=tmp_path / "data",
        downloader=_FakeDownloader(subtitle_path=None, audio_path=audio_path),
        transcriber=_FakeTranscriber(),
    )

    result = service.import_url(
        project_name="Mandarin Podcast",
        url="https://youtube.com/watch?v=abc123",
    )

    assert result.transcript_source == "openai_transcription"
