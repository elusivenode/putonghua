"""Candidate card extraction models."""

from dataclasses import dataclass
from typing import Literal, cast

CandidateType = Literal["word", "phrase", "sentence", "cloze"]


def parse_candidate_type(value: str) -> CandidateType | None:
    """Convert a runtime string into a known candidate type."""

    if value in {"word", "phrase", "sentence", "cloze"}:
        return cast(CandidateType, value)
    return None


@dataclass(frozen=True)
class CandidateDraft:
    """Candidate card fields proposed for one study chunk."""

    candidate_type: CandidateType
    simplified: str
    traditional: str
    pinyin: str
    english: str
    rationale: str
    source_excerpt: str


@dataclass(frozen=True)
class CandidateCardView:
    """Stored candidate card details for review and rendering."""

    id: str
    study_chunk_id: str | None
    candidate_type: CandidateType
    simplified: str | None
    traditional: str | None
    pinyin: str | None
    english: str | None
    status: str
    provenance_json: str


@dataclass(frozen=True)
class CandidateExtractionResult:
    """Result of extracting candidate cards for one chunk."""

    chunk_id: str
    candidate_count: int
    candidate_ids: list[str]


@dataclass(frozen=True)
class CandidatePromotionResult:
    """Result of promoting one stored review suggestion."""

    suggestion_id: str
    candidate_id: str
    status: str
    created: bool


@dataclass(frozen=True)
class CandidatePublishResult:
    """Result of publishing one durable candidate to Anki."""

    candidate_id: str
    publication_record_id: str
    anki_note_id: int
    status: str
    created: bool
