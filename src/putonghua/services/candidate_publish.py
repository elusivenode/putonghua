"""Candidate publication workflow."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from putonghua.database.connection import connect
from putonghua.database.migrations import migrate_database
from putonghua.database.repositories import (
    CandidateCardRow,
    CandidateRepository,
    PublicationRecordRepository,
)
from putonghua.models.anki import AnkiPublishNoteRequest, AnkiPublishNoteResult
from putonghua.models.candidates import CandidatePublishResult


class CandidatePublishProvider(Protocol):
    """Provider interface for publishing one note to Anki."""

    def publish_note(self, request: AnkiPublishNoteRequest) -> AnkiPublishNoteResult:
        """Create one note in Anki."""
        ...


@dataclass(frozen=True)
class CandidatePublishConfig:
    """Resolved publish target settings."""

    deck_name: str
    note_type_name: str
    publish_tags: list[str]


@dataclass(frozen=True)
class CandidatePublishService:
    """Publish promoted candidates into Anki with local idempotency."""

    database_path: Path
    provider: CandidatePublishProvider
    config: CandidatePublishConfig

    def publish_candidate(self, candidate_id: str) -> CandidatePublishResult:
        """Publish one durable candidate to Anki."""

        migrate_database(self.database_path)
        with connect(self.database_path) as connection:
            candidate_repository = CandidateRepository(connection)
            publication_repository = PublicationRecordRepository(connection)

            candidate = candidate_repository.get_candidate(candidate_id)
            if candidate is None:
                message = f"No candidate found for id {candidate_id}"
                raise ValueError(message)

            publication = publication_repository.get_by_candidate_id(candidate_id)
            if (
                publication is not None
                and publication.status == "published"
                and publication.anki_note_id is not None
            ):
                return CandidatePublishResult(
                    candidate_id=candidate_id,
                    publication_record_id=publication.id,
                    anki_note_id=int(publication.anki_note_id),
                    status="published",
                    created=False,
                )

            if candidate.status not in {"promoted", "published"}:
                message = (
                    "Candidate is not publishable. Expected status 'promoted' or "
                    f"'published', got {candidate.status!r}."
                )
                raise ValueError(message)

            publish_result = self.provider.publish_note(
                AnkiPublishNoteRequest(
                    deck_name=self.config.deck_name,
                    note_type_name=self.config.note_type_name,
                    fields=_build_note_fields(candidate),
                    tags=self.config.publish_tags,
                )
            )

            publication_id = (
                publication.id
                if publication is not None
                else publication_repository.create_publication(
                    candidate_id=candidate_id,
                    putonghua_id=candidate_id,
                    status="publishing",
                )
            )
            publication_repository.mark_published(
                publication_id,
                publish_result.note_id,
            )
            candidate_repository.update_status(candidate_id, "published")
            connection.commit()

        return CandidatePublishResult(
            candidate_id=candidate_id,
            publication_record_id=publication_id,
            anki_note_id=publish_result.note_id,
            status="published",
            created=True,
        )


def _build_note_fields(candidate: CandidateCardRow) -> dict[str, str]:
    """Convert one candidate card row into the live target note fields."""

    if candidate.simplified is None or not candidate.simplified.strip():
        raise ValueError("Candidate cannot be published without simplified text.")
    if candidate.pinyin is None or not candidate.pinyin.strip():
        raise ValueError("Candidate cannot be published without pinyin.")
    if candidate.english is None or not candidate.english.strip():
        raise ValueError("Candidate cannot be published without english gloss.")

    return {
        "Hanzi": candidate.simplified.strip(),
        "Pinyin": candidate.pinyin.strip(),
        "English": candidate.english.strip(),
        "Audio": "",
    }
