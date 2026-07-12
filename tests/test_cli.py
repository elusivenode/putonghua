from pathlib import Path
from typing import cast

from pytest import MonkeyPatch
from rich.console import Console
from typer.testing import CliRunner

from putonghua.cli.app import app

runner = CliRunner()


def test_help_command_runs() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "Interactive Mandarin card-workflow CLI" in result.stdout
    assert "--config" in result.stdout


def test_root_command_runs_tui_by_default(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "\n".join(
            [
                "app:",
                "  data_dir: .local/share/putonghua",
                "  database_path: .local/share/putonghua/putonghua.db",
                "  log_level: INFO",
            ]
        ),
        encoding="utf-8",
    )

    class _FakeService:
        pass

    def _fake_build_tui_session_service(_: Path) -> _FakeService:
        return _FakeService()

    def _fake_run_tui_session(**kwargs: object) -> None:
        assert isinstance(kwargs["service"], _FakeService)
        cast(Console, kwargs["console"]).print("TUI shell started")

    monkeypatch.setattr(
        "putonghua.cli.app._build_tui_session_service",
        _fake_build_tui_session_service,
    )
    monkeypatch.setattr("putonghua.cli.app.run_tui_session", _fake_run_tui_session)

    result = runner.invoke(app, ["--config", str(config_path)])

    assert result.exit_code == 0
    assert "TUI shell started" in result.stdout


def test_db_migrate_command_runs(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "\n".join(
            [
                "app:",
                "  data_dir: .local/share/putonghua",
                "  database_path: .local/share/putonghua/putonghua.db",
                "  log_level: INFO",
            ]
        ),
        encoding="utf-8",
    )

    result = runner.invoke(app, ["db", "migrate", "--config", str(config_path)])

    assert result.exit_code == 0
    assert "Applied migrations:" in result.stdout
    assert "001_initial" in result.stdout
    assert "002_youtube_import" in result.stdout
    assert "003_study_chunks" in result.stdout
    assert "004_study_chunk_status" in result.stdout
    assert "005_candidate_cards_by_chunk" in result.stdout
    assert "008_review_suggestions" in result.stdout
    assert "009_publication_record_uniqueness" in result.stdout


def test_tui_command_runs(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "\n".join(
            [
                "app:",
                "  data_dir: .local/share/putonghua",
                "  database_path: .local/share/putonghua/putonghua.db",
                "  log_level: INFO",
            ]
        ),
        encoding="utf-8",
    )

    class _FakeService:
        pass

    def _fake_build_tui_session_service(_: Path) -> _FakeService:
        return _FakeService()

    def _fake_run_tui_session(**kwargs: object) -> None:
        assert isinstance(kwargs["service"], _FakeService)
        cast(Console, kwargs["console"]).print("TUI shell started")

    monkeypatch.setattr(
        "putonghua.cli.app._build_tui_session_service",
        _fake_build_tui_session_service,
    )
    monkeypatch.setattr("putonghua.cli.app.run_tui_session", _fake_run_tui_session)

    result = runner.invoke(app, ["tui", "--config", str(config_path)])

    assert result.exit_code == 0
    assert "TUI shell started" in result.stdout


def test_anki_check_command_runs(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "\n".join(
            [
                "app:",
                "  data_dir: .local/share/putonghua",
                "  database_path: .local/share/putonghua/putonghua.db",
                "  log_level: INFO",
                "anki:",
                "  base_url: http://127.0.0.1:8765",
                "  api_key: null",
                "  timeout_seconds: 5.0",
            ]
        ),
        encoding="utf-8",
    )

    class _Result:
        base_url = "http://127.0.0.1:8765"
        version = 6
        deck_names = ["Default", "Mandarin"]

    class _FakeService:
        def check_connectivity(self) -> _Result:
            return _Result()

    def _fake_build_anki_discovery_service(_: Path) -> _FakeService:
        return _FakeService()

    monkeypatch.setattr(
        "putonghua.cli.app._build_anki_discovery_service",
        _fake_build_anki_discovery_service,
    )

    result = runner.invoke(app, ["anki", "check", "--config", str(config_path)])

    assert result.exit_code == 0
    assert "AnkiConnect OK" in result.stdout
    assert "Decks: Default, Mandarin" in result.stdout


def test_anki_decks_command_runs(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "\n".join(
            [
                "app:",
                "  data_dir: .local/share/putonghua",
                "  database_path: .local/share/putonghua/putonghua.db",
                "  log_level: INFO",
                "anki:",
                "  base_url: http://127.0.0.1:8765",
                "  api_key: null",
                "  timeout_seconds: 5.0",
            ]
        ),
        encoding="utf-8",
    )

    class _FakeService:
        def list_decks(self) -> list[str]:
            return ["Default", "Mandarin"]

    def _fake_build_anki_discovery_service(_: Path) -> _FakeService:
        return _FakeService()

    monkeypatch.setattr(
        "putonghua.cli.app._build_anki_discovery_service",
        _fake_build_anki_discovery_service,
    )

    result = runner.invoke(app, ["anki", "decks", "--config", str(config_path)])

    assert result.exit_code == 0
    assert "Default" in result.stdout
    assert "Mandarin" in result.stdout


def test_anki_note_types_command_runs(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "\n".join(
            [
                "app:",
                "  data_dir: .local/share/putonghua",
                "  database_path: .local/share/putonghua/putonghua.db",
                "  log_level: INFO",
                "anki:",
                "  base_url: http://127.0.0.1:8765",
                "  api_key: null",
                "  timeout_seconds: 5.0",
            ]
        ),
        encoding="utf-8",
    )

    class _FakeService:
        def list_note_types(self) -> list[str]:
            return ["Basic", "Putonghua V1"]

    def _fake_build_anki_discovery_service(_: Path) -> _FakeService:
        return _FakeService()

    monkeypatch.setattr(
        "putonghua.cli.app._build_anki_discovery_service",
        _fake_build_anki_discovery_service,
    )

    result = runner.invoke(app, ["anki", "note-types", "--config", str(config_path)])

    assert result.exit_code == 0
    assert "Basic" in result.stdout
    assert "Putonghua V1" in result.stdout


def test_anki_note_type_command_runs(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "\n".join(
            [
                "app:",
                "  data_dir: .local/share/putonghua",
                "  database_path: .local/share/putonghua/putonghua.db",
                "  log_level: INFO",
                "anki:",
                "  base_url: http://127.0.0.1:8765",
                "  api_key: null",
                "  timeout_seconds: 5.0",
            ]
        ),
        encoding="utf-8",
    )

    class _Field:
        def __init__(self, name: str, order: int) -> None:
            self.name = name
            self.order = order

    class _Template:
        def __init__(self, name: str) -> None:
            self.name = name
            self.front_template = "{{Front}}"
            self.back_template = "{{Back}}"

    class _NoteType:
        name = "Putonghua V1"
        fields = [_Field("Simplified", 0), _Field("Pinyin", 1)]
        card_templates = [_Template("Recognition"), _Template("Production")]

    class _FakeService:
        def describe_note_type(self, note_type_name: str) -> _NoteType:
            assert note_type_name == "Putonghua V1"
            return _NoteType()

    def _fake_build_anki_discovery_service(_: Path) -> _FakeService:
        return _FakeService()

    monkeypatch.setattr(
        "putonghua.cli.app._build_anki_discovery_service",
        _fake_build_anki_discovery_service,
    )

    result = runner.invoke(
        app,
        [
            "anki",
            "note-type",
            "--name",
            "Putonghua V1",
            "--config",
            str(config_path),
        ],
    )

    assert result.exit_code == 0
    assert "Note Type: Putonghua V1" in result.stdout
    assert "1. Simplified" in result.stdout
    assert "1. Recognition" in result.stdout
    assert "Front:" in result.stdout
    assert "Back:" in result.stdout


def test_candidate_publish_command_runs(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "\n".join(
            [
                "app:",
                "  data_dir: .local/share/putonghua",
                "  database_path: .local/share/putonghua/putonghua.db",
                "  log_level: INFO",
                "anki:",
                "  base_url: http://127.0.0.1:8765",
                "  api_key: null",
                "  timeout_seconds: 5.0",
                "  default_deck: Mandarin",
                "  default_note_type: Mandarin vocab",
                "  publish_tags:",
                "    - putonghua-test",
            ]
        ),
        encoding="utf-8",
    )

    class _Result:
        candidate_id = "candidate-1"
        publication_record_id = "publication-1"
        anki_note_id = 42001
        status = "published"
        created = True

    class _FakeService:
        def publish_candidate(self, candidate_id: str) -> _Result:
            assert candidate_id == "candidate-1"
            return _Result()

    def _fake_build_candidate_publish_service(
        *,
        config_path: Path,
        deck_name: str,
        note_type_name: str,
        publish_tags: list[str],
    ) -> _FakeService:
        del config_path
        assert deck_name == "Mandarin"
        assert note_type_name == "Mandarin vocab"
        assert publish_tags == ["putonghua-test"]
        return _FakeService()

    monkeypatch.setattr(
        "putonghua.cli.app._build_candidate_publish_service",
        _fake_build_candidate_publish_service,
    )

    result = runner.invoke(
        app,
        [
            "candidate",
            "publish",
            "--candidate-id",
            "candidate-1",
            "--config",
            str(config_path),
        ],
    )

    assert result.exit_code == 0
    assert "Candidate ID: candidate-1" in result.stdout
    assert "Publication Record ID: publication-1" in result.stdout
    assert "Anki Note ID: 42001" in result.stdout


def test_youtube_import_command_runs(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "\n".join(
            [
                "app:",
                "  data_dir: .local/share/putonghua",
                "  database_path: .local/share/putonghua/putonghua.db",
                "  log_level: INFO",
                "anki:",
                "  base_url: http://127.0.0.1:8765",
                "  api_key: null",
                "  timeout_seconds: 5.0",
                "openai:",
                "  api_key: null",
                "  transcription_model: whisper-1",
                "  transcription_language: zh",
                "  transcription_prompt: null",
                "  timeout_seconds: 60.0",
            ]
        ),
        encoding="utf-8",
    )

    class _Result:
        source_id = "source-1"
        project_id = "project-1"
        project_name = "Mandarin Podcast"
        title = "Episode 23"
        channel_name = "Tea with Mona"
        media_path = Path("/tmp/episode.webm")
        transcript_source = "subtitles"

    class _FakeService:
        def import_url(self, *, project_name: str, url: str) -> _Result:
            assert project_name == "Mandarin Podcast"
            assert url == "https://youtube.com/watch?v=abc123"
            return _Result()

    def _fake_migrate_database(_: Path) -> list[str]:
        return []

    def _fake_yt_dlp_downloader() -> object:
        return object()

    def _fake_youtube_import_service(**_: object) -> _FakeService:
        return _FakeService()

    monkeypatch.setattr("putonghua.cli.app.migrate_database", _fake_migrate_database)
    monkeypatch.setattr("putonghua.cli.app.YtDlpDownloader", _fake_yt_dlp_downloader)
    monkeypatch.setattr(
        "putonghua.cli.app.YouTubeImportService",
        _fake_youtube_import_service,
    )

    result = runner.invoke(
        app,
        [
            "youtube",
            "import",
            "https://youtube.com/watch?v=abc123",
            "--project-name",
            "Mandarin Podcast",
            "--config",
            str(config_path),
        ],
    )

    assert result.exit_code == 0
    assert "Imported source source-1" in result.stdout
    assert "Transcript source: subtitles" in result.stdout


def test_chunk_build_command_runs(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "\n".join(
            [
                "app:",
                "  data_dir: .local/share/putonghua",
                "  database_path: .local/share/putonghua/putonghua.db",
                "  log_level: INFO",
            ]
        ),
        encoding="utf-8",
    )

    class _Result:
        source_id = "source-1"
        chunk_count = 4
        chunk_ids = ["a", "b", "c", "d"]

    class _FakeService:
        def build_for_source(self, source_id: str, config: object) -> _Result:
            assert source_id == "source-1"
            assert config is not None
            return _Result()

    def _fake_study_chunk_service(*, database_path: Path) -> _FakeService:
        assert database_path == tmp_path / ".local/share/putonghua/putonghua.db"
        return _FakeService()

    monkeypatch.setattr(
        "putonghua.cli.app.StudyChunkService",
        _fake_study_chunk_service,
    )

    result = runner.invoke(
        app,
        [
            "chunk",
            "build",
            "--source-id",
            "source-1",
            "--config",
            str(config_path),
        ],
    )

    assert result.exit_code == 0
    assert "Built 4 study chunks" in result.stdout


def test_chunk_next_command_runs(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "\n".join(
            [
                "app:",
                "  data_dir: .local/share/putonghua",
                "  database_path: .local/share/putonghua/putonghua.db",
                "  log_level: INFO",
            ]
        ),
        encoding="utf-8",
    )

    class _Chunk:
        id = "chunk-1"
        source_id = "source-1"
        chunk_index = 0
        start_seconds = 0.0
        end_seconds = 60.0
        text = "大家好。"
        transcript_segment_count = 3
        char_count = 4
        status = "pending"
        notes = None

    class _FakeService:
        def get_next_pending_chunk(self, source_id: str) -> _Chunk | None:
            assert source_id == "source-1"
            return _Chunk()

    def _fake_study_chunk_service(**_: object) -> _FakeService:
        return _FakeService()

    monkeypatch.setattr(
        "putonghua.cli.app.StudyChunkService",
        _fake_study_chunk_service,
    )

    result = runner.invoke(
        app,
        ["chunk", "next", "--source-id", "source-1", "--config", str(config_path)],
    )

    assert result.exit_code == 0
    assert "Chunk ID: chunk-1" in result.stdout
    assert "Status: pending" in result.stdout


def test_chunk_update_command_runs(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "\n".join(
            [
                "app:",
                "  data_dir: .local/share/putonghua",
                "  database_path: .local/share/putonghua/putonghua.db",
                "  log_level: INFO",
            ]
        ),
        encoding="utf-8",
    )

    class _Result:
        chunk_id = "chunk-1"
        status = "completed"

    class _FakeService:
        def update_chunk_status(
            self,
            chunk_id: str,
            status: str,
            notes: str | None,
        ) -> _Result:
            assert chunk_id == "chunk-1"
            assert status == "completed"
            assert notes == "done"
            return _Result()

    def _fake_study_chunk_service(**_: object) -> _FakeService:
        return _FakeService()

    monkeypatch.setattr(
        "putonghua.cli.app.StudyChunkService",
        _fake_study_chunk_service,
    )

    result = runner.invoke(
        app,
        [
            "chunk",
            "update",
            "--chunk-id",
            "chunk-1",
            "--status",
            "completed",
            "--notes",
            "done",
            "--config",
            str(config_path),
        ],
    )

    assert result.exit_code == 0
    assert "Updated chunk chunk-1 to status completed" in result.stdout


def test_chunk_extract_command_requires_api_key(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "\n".join(
            [
                "app:",
                "  data_dir: .local/share/putonghua",
                "  database_path: .local/share/putonghua/putonghua.db",
                "  log_level: INFO",
                "openai:",
                "  api_key: null",
            ]
        ),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        ["chunk", "extract", "--chunk-id", "chunk-1", "--config", str(config_path)],
    )

    assert result.exit_code == 1
    assert "requires OPENAI_API_KEY" in result.stdout


def test_chunk_extract_command_runs(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "\n".join(
            [
                "app:",
                "  data_dir: .local/share/putonghua",
                "  database_path: .local/share/putonghua/putonghua.db",
                "  log_level: INFO",
                "openai:",
                "  api_key: test-key",
                "  extraction_model: gpt-4.1-mini",
                "  extraction_timeout_seconds: 90.0",
            ]
        ),
        encoding="utf-8",
    )

    class _Result:
        chunk_id = "chunk-1"
        candidate_count = 2
        candidate_ids = ["candidate-1", "candidate-2"]

    class _FakeService:
        def extract_for_chunk(self, chunk_id: str) -> _Result:
            assert chunk_id == "chunk-1"
            return _Result()

    def _fake_extraction_service(**_: object) -> _FakeService:
        return _FakeService()

    monkeypatch.setattr(
        "putonghua.cli.app.CandidateExtractionService",
        _fake_extraction_service,
    )

    result = runner.invoke(
        app,
        ["chunk", "extract", "--chunk-id", "chunk-1", "--config", str(config_path)],
    )

    assert result.exit_code == 0
    assert "Extracted 2 candidate cards for chunk chunk-1" in result.stdout


def test_chunk_candidates_command_runs(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "\n".join(
            [
                "app:",
                "  data_dir: .local/share/putonghua",
                "  database_path: .local/share/putonghua/putonghua.db",
                "  log_level: INFO",
            ]
        ),
        encoding="utf-8",
    )

    class _Row:
        id = "candidate-1"
        study_chunk_id = "chunk-1"
        candidate_type = "sentence"
        simplified = "我会尽量地把每一个字都说出来。"
        traditional = "我會盡量地把每一個字都說出來。"
        pinyin = "wǒ huì jǐn liàng de bǎ měi yí gè zì dōu shuō chū lái"
        english = "I will try my best to pronounce every word clearly."
        status = "proposed"
        provenance_json = "{}"

    class _FakeRepository:
        def __init__(self, _: object) -> None:
            pass

        def list_candidates_for_chunk(self, chunk_id: str) -> list[_Row]:
            assert chunk_id == "chunk-1"
            return [_Row()]

    class _DummyConnection:
        def __enter__(self) -> "_DummyConnection":
            return self

        def __exit__(self, *_: object) -> None:
            return None

    def _fake_migrate_database(_: Path) -> list[str]:
        return []

    def _fake_connect(_: Path) -> _DummyConnection:
        return _DummyConnection()

    monkeypatch.setattr("putonghua.cli.app.migrate_database", _fake_migrate_database)
    monkeypatch.setattr("putonghua.cli.app.connect", _fake_connect)
    monkeypatch.setattr("putonghua.cli.app.CandidateRepository", _FakeRepository)

    result = runner.invoke(
        app,
        ["chunk", "candidates", "--chunk-id", "chunk-1", "--config", str(config_path)],
    )

    assert result.exit_code == 0
    assert "Candidate ID: candidate-1" in result.stdout
    assert "Type: sentence" in result.stdout


def test_chunk_chat_command_requires_api_key(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "\n".join(
            [
                "app:",
                "  data_dir: .local/share/putonghua",
                "  database_path: .local/share/putonghua/putonghua.db",
                "  log_level: INFO",
                "openai:",
                "  api_key: null",
            ]
        ),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "chunk",
            "chat",
            "--chunk-id",
            "chunk-1",
            "--prompt",
            "Suggest a sentence card.",
            "--config",
            str(config_path),
        ],
    )

    assert result.exit_code == 1
    assert "Chunk chat requires OPENAI_API_KEY" in result.stdout


def test_chunk_chat_command_runs(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "\n".join(
            [
                "app:",
                "  data_dir: .local/share/putonghua",
                "  database_path: .local/share/putonghua/putonghua.db",
                "  log_level: INFO",
                "openai:",
                "  api_key: test-key",
                "  review_model: gpt-4.1-mini",
                "  review_timeout_seconds: 90.0",
            ]
        ),
        encoding="utf-8",
    )

    class _Result:
        conversation_id = "conversation-1"
        assistant_text = "Prioritize the full sentence."
        suggested_cards = []

    class _FakeService:
        def chat_for_chunk(self, chunk_id: str, prompt: str) -> _Result:
            assert chunk_id == "chunk-1"
            assert prompt == "Suggest a sentence card."
            return _Result()

    def _fake_chunk_review_service(**_: object) -> _FakeService:
        return _FakeService()

    monkeypatch.setattr(
        "putonghua.cli.app.ChunkReviewService",
        _fake_chunk_review_service,
    )

    result = runner.invoke(
        app,
        [
            "chunk",
            "chat",
            "--chunk-id",
            "chunk-1",
            "--prompt",
            "Suggest a sentence card.",
            "--config",
            str(config_path),
        ],
    )

    assert result.exit_code == 0
    assert "Conversation ID: conversation-1" in result.stdout
    assert "Prioritize the full sentence." in result.stdout


def test_chunk_suggestions_command_runs(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "\n".join(
            [
                "app:",
                "  data_dir: .local/share/putonghua",
                "  database_path: .local/share/putonghua/putonghua.db",
                "  log_level: INFO",
            ]
        ),
        encoding="utf-8",
    )

    class _Suggestion:
        id = "suggestion-1"
        conversation_id = "conversation-1"
        suggestion_index = 0
        candidate_type = "sentence"
        status = "suggested"
        simplified = "我会尽量地把每一个字都说出来。"
        traditional = "我會盡量地把每一個字都說出來。"
        pinyin = "wǒ huì jǐn liàng de bǎ měi yí gè zì dōu shuō chū lái"
        english = "I will try my best to pronounce every word clearly."
        rationale = "Good full-sentence listening support card."
        source_excerpt = "我会尽量地把每一个字都说出来"

    class _FakeService:
        def list_review_suggestions(self, conversation_id: str) -> list[_Suggestion]:
            assert conversation_id == "conversation-1"
            return [_Suggestion()]

    def _fake_review_suggestion_service(**_: object) -> _FakeService:
        return _FakeService()

    monkeypatch.setattr(
        "putonghua.cli.app.ReviewSuggestionService",
        _fake_review_suggestion_service,
    )

    result = runner.invoke(
        app,
        [
            "chunk",
            "suggestions",
            "--conversation-id",
            "conversation-1",
            "--config",
            str(config_path),
        ],
    )

    assert result.exit_code == 0
    assert "Suggestion ID: suggestion-1" in result.stdout
    assert "Type: sentence" in result.stdout
    assert "Status: suggested" in result.stdout


def test_chunk_promote_command_runs(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "\n".join(
            [
                "app:",
                "  data_dir: .local/share/putonghua",
                "  database_path: .local/share/putonghua/putonghua.db",
                "  log_level: INFO",
            ]
        ),
        encoding="utf-8",
    )

    class _Result:
        suggestion_id = "suggestion-1"
        candidate_id = "candidate-1"
        status = "promoted"
        created = True

    class _FakeService:
        def promote_suggestion(self, suggestion_id: str) -> _Result:
            assert suggestion_id == "suggestion-1"
            return _Result()

    def _fake_review_suggestion_service(**_: object) -> _FakeService:
        return _FakeService()

    monkeypatch.setattr(
        "putonghua.cli.app.ReviewSuggestionService",
        _fake_review_suggestion_service,
    )

    result = runner.invoke(
        app,
        [
            "chunk",
            "promote",
            "--suggestion-id",
            "suggestion-1",
            "--config",
            str(config_path),
        ],
    )

    assert result.exit_code == 0
    assert "Suggestion ID: suggestion-1" in result.stdout
    assert "Candidate ID: candidate-1" in result.stdout
    assert "Status: promoted" in result.stdout
