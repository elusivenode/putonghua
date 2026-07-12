"""Minimal CLI entry point."""

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from putonghua import __version__
from putonghua.config.loader import load_settings
from putonghua.database.connection import connect
from putonghua.database.migrations import migrate_database
from putonghua.database.repositories import CandidateRepository
from putonghua.logging import configure_logging
from putonghua.models.anki import AnkiNoteTypeView
from putonghua.models.candidates import (
    CandidateCardView,
    CandidateDraft,
    CandidatePublishResult,
    parse_candidate_type,
)
from putonghua.models.chunks import StudyChunkView
from putonghua.models.review import ReviewSuggestionView
from putonghua.providers.anki_connect import AnkiConnectConfig, AnkiConnectProvider
from putonghua.providers.openai_candidate_extraction import (
    OpenAICandidateExtractionConfig,
    OpenAICandidateExtractionProvider,
)
from putonghua.providers.openai_chunk_review import (
    OpenAIChunkReviewConfig,
    OpenAIChunkReviewProvider,
)
from putonghua.providers.openai_transcription import (
    OpenAITranscriptionConfig,
    OpenAITranscriptionProvider,
)
from putonghua.services.anki_discovery import AnkiDiscoveryService
from putonghua.services.candidate_extraction import CandidateExtractionService
from putonghua.services.candidate_publish import (
    CandidatePublishConfig,
    CandidatePublishService,
)
from putonghua.services.chunk_review import ChunkReviewService
from putonghua.services.review_suggestions import ReviewSuggestionService
from putonghua.services.study_chunks import (
    StudyChunkBuildConfig,
    StudyChunkService,
)
from putonghua.services.youtube_import import (
    YouTubeImportService,
    YtDlpDownloader,
)

app = typer.Typer(
    name="putonghua",
    help="Repository foundation commands for the putonghua project.",
    no_args_is_help=True,
)
db_app = typer.Typer(help="Database maintenance commands.")
anki_app = typer.Typer(help="AnkiConnect commands.")
youtube_app = typer.Typer(help="YouTube source import commands.")
chunk_app = typer.Typer(help="Study chunk commands.")
candidate_app = typer.Typer(help="Candidate card commands.")
console = Console()
DEFAULT_CONFIG_PATH = Path("config.yaml")
ConfigOption = Annotated[
    Path,
    typer.Option(
        "--config",
        help="Path to the YAML configuration file.",
    ),
]

app.add_typer(db_app, name="db")
app.add_typer(anki_app, name="anki")
app.add_typer(youtube_app, name="youtube")
app.add_typer(chunk_app, name="chunk")
app.add_typer(candidate_app, name="candidate")


@app.callback()
def main_callback() -> None:
    """Run the top-level CLI."""


@app.command("version")
def version() -> None:
    """Print the package version."""

    console.print(__version__)


@app.command("init")
def init(config_path: ConfigOption = DEFAULT_CONFIG_PATH) -> None:
    """Validate configuration and initialize local directories."""

    settings = load_settings(config_path)
    configure_logging(settings.app.log_level)
    settings.app.data_dir.mkdir(parents=True, exist_ok=True)
    console.print(f"Initialized data directory at {settings.app.data_dir}")


@db_app.command("migrate")
def migrate(config_path: ConfigOption = DEFAULT_CONFIG_PATH) -> None:
    """Apply pending SQLite migrations."""

    settings = load_settings(config_path)
    configure_logging(settings.app.log_level)
    applied = migrate_database(settings.app.database_path)
    if applied:
        console.print(f"Applied migrations: {', '.join(applied)}")
        return
    console.print("No pending migrations.")


@anki_app.command("check")
def anki_check(config_path: ConfigOption = DEFAULT_CONFIG_PATH) -> None:
    """Verify that AnkiConnect is reachable and can read deck names."""

    settings = load_settings(config_path)
    configure_logging(settings.app.log_level)
    service = _build_anki_discovery_service(config_path)
    try:
        result = service.check_connectivity()
    except Exception as exc:
        console.print(f"AnkiConnect check failed: {exc}")
        raise typer.Exit(code=1) from exc

    deck_names = ", ".join(result.deck_names) if result.deck_names else "(none)"
    console.print(f"AnkiConnect OK at {result.base_url}")
    console.print(f"Version: {result.version}")
    console.print(f"Decks: {deck_names}")


@anki_app.command("decks")
def anki_decks(config_path: ConfigOption = DEFAULT_CONFIG_PATH) -> None:
    """List available Anki deck names."""

    settings = load_settings(config_path)
    configure_logging(settings.app.log_level)
    service = _build_anki_discovery_service(config_path)
    try:
        deck_names = service.list_decks()
    except Exception as exc:
        console.print(f"Anki deck listing failed: {exc}")
        raise typer.Exit(code=1) from exc

    if not deck_names:
        console.print("No Anki decks found")
        return

    for deck_name in deck_names:
        console.print(deck_name)


@anki_app.command("note-types")
def anki_note_types(config_path: ConfigOption = DEFAULT_CONFIG_PATH) -> None:
    """List available Anki note type names."""

    settings = load_settings(config_path)
    configure_logging(settings.app.log_level)
    service = _build_anki_discovery_service(config_path)
    try:
        note_type_names = service.list_note_types()
    except Exception as exc:
        console.print(f"Anki note type listing failed: {exc}")
        raise typer.Exit(code=1) from exc

    if not note_type_names:
        console.print("No Anki note types found")
        return

    for note_type_name in note_type_names:
        console.print(note_type_name)


@anki_app.command("note-type")
def anki_note_type(
    name: str = typer.Option(..., "--name", help="Anki note type name."),
    config_path: ConfigOption = DEFAULT_CONFIG_PATH,
) -> None:
    """Describe one Anki note type."""

    settings = load_settings(config_path)
    configure_logging(settings.app.log_level)
    service = _build_anki_discovery_service(config_path)
    try:
        note_type = service.describe_note_type(name)
    except Exception as exc:
        console.print(f"Anki note type inspection failed: {exc}")
        raise typer.Exit(code=1) from exc

    _render_anki_note_type(note_type)


@candidate_app.command("publish")
def candidate_publish(
    candidate_id: Annotated[
        str,
        typer.Option("--candidate-id", help="Candidate identifier."),
    ],
    deck: Annotated[
        str | None,
        typer.Option("--deck", help="Override target Anki deck for this publish."),
    ] = None,
    note_type: Annotated[
        str | None,
        typer.Option(
            "--note-type",
            help="Override target Anki note type for this publish.",
        ),
    ] = None,
    tag: Annotated[
        list[str] | None,
        typer.Option("--tag", help="Additional publish tag. Repeat for multiple tags."),
    ] = None,
    config_path: ConfigOption = DEFAULT_CONFIG_PATH,
) -> None:
    """Publish one durable candidate to the configured Anki target."""

    settings = load_settings(config_path)
    configure_logging(settings.app.log_level)
    target_deck = deck or settings.anki.default_deck
    target_note_type = note_type or settings.anki.default_note_type
    if target_deck is None:
        console.print("Candidate publish requires --deck or anki.default_deck.")
        raise typer.Exit(code=1)
    if target_note_type is None:
        console.print(
            "Candidate publish requires --note-type or anki.default_note_type."
        )
        raise typer.Exit(code=1)

    tags = list(settings.anki.publish_tags)
    if tag:
        tags.extend(tag)

    service = _build_candidate_publish_service(
        config_path=config_path,
        deck_name=target_deck,
        note_type_name=target_note_type,
        publish_tags=tags,
    )
    try:
        result = service.publish_candidate(candidate_id)
    except Exception as exc:
        console.print(f"Candidate publish failed: {exc}")
        raise typer.Exit(code=1) from exc

    _render_candidate_publish_result(result)


@youtube_app.command("import")
def youtube_import(
    url: str = typer.Argument(..., help="YouTube episode URL to import."),
    project_name: str = typer.Option(
        ...,
        "--project-name",
        help="Project name to create or reuse for this source.",
    ),
    config_path: ConfigOption = DEFAULT_CONFIG_PATH,
) -> None:
    """Import one YouTube episode, preferring subtitles before transcription."""

    settings = load_settings(config_path)
    configure_logging(settings.app.log_level)
    migrate_database(settings.app.database_path)

    transcriber = None
    if settings.openai.api_key:
        transcriber = OpenAITranscriptionProvider(
            OpenAITranscriptionConfig(
                api_key=settings.openai.api_key,
                model=settings.openai.transcription_model,
                language=settings.openai.transcription_language,
                prompt=settings.openai.transcription_prompt,
                timeout_seconds=settings.openai.timeout_seconds,
                max_upload_bytes=settings.openai.max_upload_bytes,
                transcription_bitrate_kbps=settings.openai.transcription_bitrate_kbps,
                chunk_duration_seconds=settings.openai.chunk_duration_seconds,
            )
        )

    service = YouTubeImportService(
        database_path=settings.app.database_path,
        data_dir=settings.app.data_dir,
        downloader=YtDlpDownloader(),
        transcriber=transcriber,
    )

    try:
        result = service.import_url(project_name=project_name, url=url)
    except Exception as exc:
        console.print(f"YouTube import failed: {exc}")
        raise typer.Exit(code=1) from exc

    console.print(f"Imported source {result.source_id}")
    console.print(f"Project: {result.project_name} ({result.project_id})")
    console.print(f"Title: {result.title}")
    if result.channel_name:
        console.print(f"Channel: {result.channel_name}")
    console.print(f"Audio: {result.media_path}")
    console.print(f"Transcript source: {result.transcript_source}")


@chunk_app.command("build")
def chunk_build(
    source_id: str = typer.Option(..., "--source-id", help="Source identifier."),
    max_duration_seconds: float = typer.Option(
        90.0,
        "--max-duration-seconds",
        help="Maximum audio span per study chunk.",
    ),
    max_char_count: int = typer.Option(
        700,
        "--max-char-count",
        help="Maximum character count per study chunk.",
    ),
    min_duration_seconds: float = typer.Option(
        25.0,
        "--min-duration-seconds",
        help="Preferred minimum duration before closing at a sentence boundary.",
    ),
    min_char_count: int = typer.Option(
        140,
        "--min-char-count",
        help="Preferred minimum character count before closing at a sentence boundary.",
    ),
    config_path: ConfigOption = DEFAULT_CONFIG_PATH,
) -> None:
    """Build study chunks from transcript segments for one source."""

    settings = load_settings(config_path)
    configure_logging(settings.app.log_level)
    service = StudyChunkService(database_path=settings.app.database_path)
    try:
        result = service.build_for_source(
            source_id,
            StudyChunkBuildConfig(
                max_duration_seconds=max_duration_seconds,
                max_char_count=max_char_count,
                min_duration_seconds=min_duration_seconds,
                min_char_count=min_char_count,
            ),
        )
    except Exception as exc:
        console.print(f"Study chunk build failed: {exc}")
        raise typer.Exit(code=1) from exc

    console.print(
        f"Built {result.chunk_count} study chunks for source {result.source_id}"
    )


@chunk_app.command("next")
def chunk_next(
    source_id: str = typer.Option(..., "--source-id", help="Source identifier."),
    config_path: ConfigOption = DEFAULT_CONFIG_PATH,
) -> None:
    """Show the next pending study chunk for a source."""

    settings = load_settings(config_path)
    configure_logging(settings.app.log_level)
    service = StudyChunkService(database_path=settings.app.database_path)
    chunk = service.get_next_pending_chunk(source_id)
    if chunk is None:
        console.print(f"No pending chunks for source {source_id}")
        return
    _render_chunk(chunk)


@chunk_app.command("show")
def chunk_show(
    chunk_id: str = typer.Option(..., "--chunk-id", help="Study chunk identifier."),
    config_path: ConfigOption = DEFAULT_CONFIG_PATH,
) -> None:
    """Show one study chunk."""

    settings = load_settings(config_path)
    configure_logging(settings.app.log_level)
    service = StudyChunkService(database_path=settings.app.database_path)
    chunk = service.get_chunk(chunk_id)
    if chunk is None:
        console.print(f"No study chunk found for id {chunk_id}")
        raise typer.Exit(code=1)
    _render_chunk(chunk)


@chunk_app.command("update")
def chunk_update(
    chunk_id: str = typer.Option(..., "--chunk-id", help="Study chunk identifier."),
    status: str = typer.Option(
        ...,
        "--status",
        help="New status: pending, in_review, completed, skipped.",
    ),
    notes: str | None = typer.Option(
        None,
        "--notes",
        help="Optional review notes.",
    ),
    config_path: ConfigOption = DEFAULT_CONFIG_PATH,
) -> None:
    """Update study chunk status."""

    settings = load_settings(config_path)
    configure_logging(settings.app.log_level)
    service = StudyChunkService(database_path=settings.app.database_path)
    try:
        result = service.update_chunk_status(chunk_id, status, notes)
    except Exception as exc:
        console.print(f"Study chunk update failed: {exc}")
        raise typer.Exit(code=1) from exc

    console.print(f"Updated chunk {result.chunk_id} to status {result.status}")


@chunk_app.command("extract")
def chunk_extract(
    chunk_id: str = typer.Option(..., "--chunk-id", help="Study chunk identifier."),
    config_path: ConfigOption = DEFAULT_CONFIG_PATH,
) -> None:
    """Extract candidate cards for one chunk."""

    settings = load_settings(config_path)
    configure_logging(settings.app.log_level)
    if not settings.openai.api_key:
        console.print("Chunk extraction requires OPENAI_API_KEY or openai.api_key.")
        raise typer.Exit(code=1)

    service = CandidateExtractionService(
        database_path=settings.app.database_path,
        provider=OpenAICandidateExtractionProvider(
            OpenAICandidateExtractionConfig(
                api_key=settings.openai.api_key,
                model=settings.openai.extraction_model,
                timeout_seconds=settings.openai.extraction_timeout_seconds,
            )
        ),
    )

    try:
        result = service.extract_for_chunk(chunk_id)
    except Exception as exc:
        console.print(f"Chunk extraction failed: {exc}")
        raise typer.Exit(code=1) from exc

    console.print(
        "Extracted "
        f"{result.candidate_count} candidate cards for chunk {result.chunk_id}"
    )


@chunk_app.command("candidates")
def chunk_candidates(
    chunk_id: str = typer.Option(..., "--chunk-id", help="Study chunk identifier."),
    config_path: ConfigOption = DEFAULT_CONFIG_PATH,
) -> None:
    """List persisted candidate cards for one chunk."""

    settings = load_settings(config_path)
    configure_logging(settings.app.log_level)
    migrate_database(settings.app.database_path)
    with connect(settings.app.database_path) as connection:
        repository = CandidateRepository(connection)
        rows = repository.list_candidates_for_chunk(chunk_id)

    candidates = [
        CandidateCardView(
            id=row.id,
            study_chunk_id=row.study_chunk_id,
            candidate_type=parse_candidate_type(row.candidate_type) or "word",
            simplified=row.simplified,
            traditional=row.traditional,
            pinyin=row.pinyin,
            english=row.english,
            status=row.status,
            provenance_json=row.provenance_json,
        )
        for row in rows
    ]
    if not candidates:
        console.print(f"No candidate cards found for chunk {chunk_id}")
        return

    for candidate in candidates:
        _render_candidate_card(candidate)


@chunk_app.command("chat")
def chunk_chat(
    chunk_id: str = typer.Option(..., "--chunk-id", help="Study chunk identifier."),
    prompt: str = typer.Option(..., "--prompt", help="Learner prompt for the chunk."),
    config_path: ConfigOption = DEFAULT_CONFIG_PATH,
) -> None:
    """Chat with the review model about one chunk."""

    settings = load_settings(config_path)
    configure_logging(settings.app.log_level)
    if not settings.openai.api_key:
        console.print("Chunk chat requires OPENAI_API_KEY or openai.api_key.")
        raise typer.Exit(code=1)

    service = ChunkReviewService(
        database_path=settings.app.database_path,
        provider=OpenAIChunkReviewProvider(
            OpenAIChunkReviewConfig(
                api_key=settings.openai.api_key,
                model=settings.openai.review_model,
                timeout_seconds=settings.openai.review_timeout_seconds,
            )
        ),
        provider_name="openai",
        model_name=settings.openai.review_model,
    )

    try:
        result = service.chat_for_chunk(chunk_id, prompt)
    except Exception as exc:
        console.print(f"Chunk chat failed: {exc}")
        raise typer.Exit(code=1) from exc

    console.print(f"Conversation ID: {result.conversation_id}")
    console.print("Assistant:")
    console.print(result.assistant_text)
    if result.suggested_cards:
        console.print("Suggested Cards:")
        for card in result.suggested_cards:
            _render_candidate_draft(card)


@chunk_app.command("suggestions")
def chunk_suggestions(
    conversation_id: str = typer.Option(
        ...,
        "--conversation-id",
        help="Review conversation identifier.",
    ),
    config_path: ConfigOption = DEFAULT_CONFIG_PATH,
) -> None:
    """List persisted review suggestions for one conversation."""

    settings = load_settings(config_path)
    configure_logging(settings.app.log_level)
    service = ReviewSuggestionService(database_path=settings.app.database_path)
    try:
        suggestions = service.list_review_suggestions(conversation_id)
    except Exception as exc:
        console.print(f"Chunk suggestion listing failed: {exc}")
        raise typer.Exit(code=1) from exc

    if not suggestions:
        console.print(f"No review suggestions found for conversation {conversation_id}")
        return

    for suggestion in suggestions:
        _render_review_suggestion(suggestion)


@chunk_app.command("promote")
def chunk_promote(
    suggestion_id: str = typer.Option(
        ...,
        "--suggestion-id",
        help="Stored review suggestion identifier.",
    ),
    config_path: ConfigOption = DEFAULT_CONFIG_PATH,
) -> None:
    """Promote one stored review suggestion into a durable candidate."""

    settings = load_settings(config_path)
    configure_logging(settings.app.log_level)
    service = ReviewSuggestionService(database_path=settings.app.database_path)
    try:
        result = service.promote_suggestion(suggestion_id)
    except Exception as exc:
        console.print(f"Chunk promotion failed: {exc}")
        raise typer.Exit(code=1) from exc

    console.print(f"Suggestion ID: {result.suggestion_id}")
    console.print(f"Candidate ID: {result.candidate_id}")
    console.print(f"Status: {result.status}")
    if result.created:
        console.print("Created new candidate")
    else:
        console.print("Candidate already existed")


def _render_chunk(chunk: StudyChunkView) -> None:
    """Render a chunk-like object to the terminal."""

    console.print(f"Chunk ID: {chunk.id}")
    console.print(f"Source ID: {chunk.source_id}")
    console.print(f"Chunk Index: {chunk.chunk_index}")
    console.print(f"Time Range: {chunk.start_seconds:.2f}s - {chunk.end_seconds:.2f}s")
    console.print(f"Status: {chunk.status}")
    console.print(f"Segments: {chunk.transcript_segment_count}")
    console.print(f"Chars: {chunk.char_count}")
    if chunk.notes:
        console.print(f"Notes: {chunk.notes}")
    console.print("Text:")
    console.print(chunk.text)


def _render_candidate_card(candidate: CandidateCardView) -> None:
    """Render one persisted candidate card."""

    console.print(f"Candidate ID: {candidate.id}")
    console.print(f"Type: {candidate.candidate_type}")
    console.print(f"Status: {candidate.status}")
    console.print(f"Simplified: {candidate.simplified or ''}")
    console.print(f"Traditional: {candidate.traditional or ''}")
    console.print(f"Pinyin: {candidate.pinyin or ''}")
    console.print(f"English: {candidate.english or ''}")


def _render_candidate_draft(card: CandidateDraft) -> None:
    """Render one suggested candidate draft."""

    console.print(f"Type: {card.candidate_type}")
    console.print(f"Simplified: {card.simplified}")
    console.print(f"Traditional: {card.traditional}")
    console.print(f"Pinyin: {card.pinyin}")
    console.print(f"English: {card.english}")
    console.print(f"Rationale: {card.rationale}")
    console.print(f"Excerpt: {card.source_excerpt}")


def _render_review_suggestion(suggestion: ReviewSuggestionView) -> None:
    """Render one persisted review suggestion."""

    console.print(f"Suggestion ID: {suggestion.id}")
    console.print(f"Conversation ID: {suggestion.conversation_id}")
    console.print(f"Index: {suggestion.suggestion_index}")
    console.print(f"Type: {suggestion.candidate_type}")
    console.print(f"Status: {suggestion.status}")
    console.print(f"Simplified: {suggestion.simplified}")
    console.print(f"Traditional: {suggestion.traditional}")
    console.print(f"Pinyin: {suggestion.pinyin}")
    console.print(f"English: {suggestion.english}")
    console.print(f"Rationale: {suggestion.rationale}")
    console.print(f"Excerpt: {suggestion.source_excerpt}")


def _build_anki_discovery_service(config_path: Path) -> AnkiDiscoveryService:
    """Build the Anki discovery service from config."""

    settings = load_settings(config_path)
    return AnkiDiscoveryService(
        provider=AnkiConnectProvider(
            AnkiConnectConfig(
                base_url=settings.anki.base_url,
                timeout_seconds=settings.anki.timeout_seconds,
                api_key=settings.anki.api_key,
            )
        )
    )


def _build_candidate_publish_service(
    *,
    config_path: Path,
    deck_name: str,
    note_type_name: str,
    publish_tags: list[str],
) -> CandidatePublishService:
    """Build the candidate publish service from config."""

    settings = load_settings(config_path)
    return CandidatePublishService(
        database_path=settings.app.database_path,
        provider=AnkiConnectProvider(
            AnkiConnectConfig(
                base_url=settings.anki.base_url,
                timeout_seconds=settings.anki.timeout_seconds,
                api_key=settings.anki.api_key,
            )
        ),
        config=CandidatePublishConfig(
            deck_name=deck_name,
            note_type_name=note_type_name,
            publish_tags=publish_tags,
        ),
    )


def _render_anki_note_type(note_type: AnkiNoteTypeView) -> None:
    """Render one Anki note type description."""

    console.print(f"Note Type: {note_type.name}")
    console.print("Fields:")
    for field in note_type.fields:
        console.print(f"{field.order + 1}. {field.name}")

    console.print("Card Templates:")
    for index, template in enumerate(note_type.card_templates, start=1):
        console.print(f"{index}. {template.name}")
        console.print(f"   Front: {_compact_template(template.front_template)}")
        console.print(f"   Back: {_compact_template(template.back_template)}")


def _compact_template(template: str, *, limit: int = 80) -> str:
    """Render one card template body on a single readable line."""

    compact = " ".join(template.split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3] + "..."


def _render_candidate_publish_result(result: CandidatePublishResult) -> None:
    """Render one candidate publish result."""

    console.print(f"Candidate ID: {result.candidate_id}")
    console.print(f"Publication Record ID: {result.publication_record_id}")
    console.print(f"Anki Note ID: {result.anki_note_id}")
    console.print(f"Status: {result.status}")
    if result.created:
        console.print("Created new Anki note")
    else:
        console.print("Anki note already existed locally")


def main() -> None:
    """Run the CLI application."""

    app()


if __name__ == "__main__":
    main()
