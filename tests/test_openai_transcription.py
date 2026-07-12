from pathlib import Path

from pytest import MonkeyPatch

import putonghua.providers.openai_transcription as openai_transcription
from putonghua.providers.openai_transcription import (
    OpenAITranscriptionConfig,
    prepare_audio_paths_for_transcription,
)


def _config() -> OpenAITranscriptionConfig:
    return OpenAITranscriptionConfig(
        api_key="test-key",
        model="whisper-1",
        language="zh",
        prompt=None,
        timeout_seconds=60.0,
        max_upload_bytes=24_000_000,
        transcription_bitrate_kbps=64,
        chunk_duration_seconds=480,
    )


def test_prepare_audio_paths_returns_original_when_small(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    audio_path = tmp_path / "small.webm"
    audio_path.write_bytes(b"small-audio")
    config = _config()

    def _fake_which(_: str) -> None:
        return None

    monkeypatch.setattr(openai_transcription.shutil, "which", _fake_which)

    result = prepare_audio_paths_for_transcription(
        config=config,
        audio_path=audio_path,
    )

    assert result == [audio_path]


def test_prepare_audio_paths_chunks_large_audio(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    audio_path = tmp_path / "large.webm"
    audio_path.write_bytes(b"x" * 30_000_000)
    config = _config()

    transcription_dir = audio_path.parent / "transcription"
    chunk_dir = transcription_dir / "chunks"
    chunk_a = chunk_dir / "chunk_000.mp3"
    chunk_b = chunk_dir / "chunk_001.mp3"

    def _fake_which(_: str) -> str:
        return "/opt/homebrew/bin/ffmpeg"

    monkeypatch.setattr(openai_transcription.shutil, "which", _fake_which)

    def _fake_transcode_audio(
        *,
        source_path: Path,
        output_path: Path,
        bitrate_kbps: int,
    ) -> None:
        assert source_path == audio_path
        assert bitrate_kbps == 64
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"y" * 26_000_000)

    def _fake_subprocess_run(
        args: list[str],
        *,
        check: bool,
        capture_output: bool,
        text: bool,
    ) -> object:
        del check, capture_output, text
        if args[0] == "ffmpeg" and "-f" in args and "segment" in args:
            chunk_dir.mkdir(parents=True, exist_ok=True)
            chunk_a.write_bytes(b"a" * 5_000_000)
            chunk_b.write_bytes(b"b" * 4_000_000)
            return object()
        raise AssertionError(f"Unexpected subprocess call: {args}")

    monkeypatch.setattr(
        openai_transcription,
        "_transcode_audio",
        _fake_transcode_audio,
    )
    monkeypatch.setattr(
        openai_transcription.subprocess,
        "run",
        _fake_subprocess_run,
    )

    result = prepare_audio_paths_for_transcription(
        config=config,
        audio_path=audio_path,
    )

    assert result == [chunk_a, chunk_b]
