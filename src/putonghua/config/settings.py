"""Typed settings models."""

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class AppSettings(BaseModel):
    """Application-level settings."""

    model_config = ConfigDict(frozen=True)

    data_dir: Path
    database_path: Path
    log_level: str = "INFO"


class AnkiSettings(BaseModel):
    """AnkiConnect settings."""

    model_config = ConfigDict(frozen=True)

    base_url: str = "http://127.0.0.1:8765"
    api_key: str | None = None
    timeout_seconds: float = 5.0
    default_deck: str | None = None
    default_note_type: str | None = None
    publish_tags: list[str] = Field(default_factory=list)


class OpenAISettings(BaseModel):
    """OpenAI provider settings."""

    model_config = ConfigDict(frozen=True)

    api_key: str | None = None
    transcription_model: str = "whisper-1"
    transcription_language: str = "zh"
    transcription_prompt: str | None = None
    timeout_seconds: float = 300.0
    max_upload_bytes: int = 24_000_000
    transcription_bitrate_kbps: int = 64
    chunk_duration_seconds: int = 480
    extraction_model: str = "gpt-4.1-mini"
    extraction_timeout_seconds: float = 120.0
    review_model: str = "gpt-4.1-mini"
    review_timeout_seconds: float = 120.0


class Settings(BaseModel):
    """Root settings object."""

    model_config = ConfigDict(frozen=True)

    app: AppSettings
    anki: AnkiSettings = AnkiSettings()
    openai: OpenAISettings = OpenAISettings()
