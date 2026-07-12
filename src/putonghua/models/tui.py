"""Read models for the terminal session shell."""

from dataclasses import dataclass

from putonghua.models.tutorial import TutorialSessionView


@dataclass(frozen=True)
class TuiProjectView:
    """Project summary for session navigation."""

    id: str
    name: str
    source_count: int


@dataclass(frozen=True)
class TuiSourceView:
    """Source summary for session navigation."""

    id: str
    project_id: str
    title: str
    source_type: str
    transcript_source: str | None
    candidate_count: int
    chunk_count: int
    pending_chunk_count: int


@dataclass(frozen=True)
class TuiChunkView:
    """Chunk summary for session navigation."""

    id: str
    source_id: str
    chunk_index: int
    status: str
    char_count: int
    candidate_count: int
    start_seconds: float
    end_seconds: float
    text: str


@dataclass(frozen=True)
class TuiReviewMessageView:
    """Persisted review message summary for the selected chunk."""

    role: str
    content: str


@dataclass(frozen=True)
class TuiReviewContextView:
    """Latest persisted review context for the selected chunk."""

    conversation_id: str
    messages: list[TuiReviewMessageView]


@dataclass(frozen=True)
class TuiCandidateView:
    """Persisted candidate summary for the selected chunk."""

    id: str
    candidate_type: str
    simplified: str | None
    english: str | None
    status: str
    publication_status: str | None
    anki_note_id: int | None


@dataclass(frozen=True)
class TuiPublishTargetView:
    """Resolved publish target visible in the interactive session."""

    deck_name: str
    note_type_name: str
    publish_tags: list[str]


@dataclass(frozen=True)
class TuiDashboardView:
    """Current interactive session dashboard state."""

    selected_project_id: str | None
    selected_source_id: str | None
    selected_chunk_id: str | None
    projects: list[TuiProjectView]
    sources: list[TuiSourceView]
    chunks: list[TuiChunkView]
    candidates: list[TuiCandidateView]
    review_context: TuiReviewContextView | None
    publish_target: TuiPublishTargetView | None
    tutorial: TutorialSessionView | None = None
