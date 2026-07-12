"""Chunk review conversation models."""

from dataclasses import dataclass

from putonghua.models.candidates import CandidateDraft


@dataclass(frozen=True)
class ReviewConversationView:
    """Persisted conversation metadata for one chunk."""

    id: str
    study_chunk_id: str
    provider: str
    model: str
    prompt_version: str


@dataclass(frozen=True)
class ReviewMessageView:
    """One persisted review conversation message."""

    id: str
    conversation_id: str
    role: str
    content: str


@dataclass(frozen=True)
class ReviewSuggestionView:
    """One persisted structured review suggestion."""

    id: str
    conversation_id: str
    study_chunk_id: str
    source_message_id: str | None
    suggestion_index: int
    candidate_type: str
    simplified: str
    traditional: str
    pinyin: str
    english: str
    rationale: str
    source_excerpt: str
    status: str
    promoted_candidate_card_id: str | None


@dataclass(frozen=True)
class ChunkReviewResponse:
    """Provider response for a chunk review chat turn."""

    assistant_text: str
    suggested_cards: list[CandidateDraft]


@dataclass(frozen=True)
class ChunkChatResult:
    """Service result for one chunk chat turn."""

    conversation_id: str
    assistant_text: str
    suggested_cards: list[CandidateDraft]
