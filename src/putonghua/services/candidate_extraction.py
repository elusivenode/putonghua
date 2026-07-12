"""Candidate extraction over study chunks."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from putonghua.database.connection import connect
from putonghua.database.migrations import migrate_database
from putonghua.database.repositories import (
    CandidateCardCreateRecord,
    CandidateRepository,
    SourceRepository,
    StudyChunkRepository,
)
from putonghua.models.candidates import CandidateDraft, CandidateExtractionResult
from putonghua.models.chunks import StudyChunkView


class CandidateExtractionProvider(Protocol):
    """Provider interface for chunk candidate extraction."""

    def extract_candidates(self, chunk: StudyChunkView) -> list[CandidateDraft]:
        """Return candidate drafts for one chunk."""
        ...


@dataclass(frozen=True)
class CandidateExtractionService:
    """Chunk-scoped candidate extraction workflow."""

    database_path: Path
    provider: CandidateExtractionProvider

    def extract_for_chunk(self, chunk_id: str) -> CandidateExtractionResult:
        """Extract and persist candidate cards for one study chunk."""

        migrate_database(self.database_path)
        with connect(self.database_path) as connection:
            chunk_repository = StudyChunkRepository(connection)
            source_repository = SourceRepository(connection)
            candidate_repository = CandidateRepository(connection)

            chunk_row = chunk_repository.get_chunk(chunk_id)
            if chunk_row is None:
                message = f"No study chunk found for id {chunk_id}"
                raise ValueError(message)

            chunk = StudyChunkView(
                id=chunk_row.id,
                source_id=chunk_row.source_id,
                chunk_index=chunk_row.chunk_index,
                start_seconds=chunk_row.start_seconds,
                end_seconds=chunk_row.end_seconds,
                text=chunk_row.text,
                transcript_segment_count=chunk_row.transcript_segment_count,
                char_count=chunk_row.char_count,
                status=chunk_row.status,
                last_reviewed_at=chunk_row.last_reviewed_at,
                notes=chunk_row.notes,
            )
            source = source_repository.get_source_context(chunk.source_id)
            if source is None:
                message = f"No source found for chunk {chunk_id}"
                raise ValueError(message)

            drafts = self.provider.extract_candidates(chunk)
            records = [
                CandidateCardCreateRecord(
                    project_id=source.project_id,
                    source_id=source.id,
                    study_chunk_id=chunk.id,
                    candidate_type=draft.candidate_type,
                    simplified=draft.simplified,
                    traditional=draft.traditional,
                    pinyin=draft.pinyin,
                    english=draft.english,
                    provenance={
                        "provider": self.provider.__class__.__name__,
                        "chunk_id": chunk.id,
                        "chunk_index": chunk.chunk_index,
                        "candidate_type": draft.candidate_type,
                        "source_excerpt": draft.source_excerpt,
                        "rationale": draft.rationale,
                    },
                )
                for draft in drafts
            ]
            candidate_ids = candidate_repository.create_candidates(records)

        return CandidateExtractionResult(
            chunk_id=chunk_id,
            candidate_count=len(candidate_ids),
            candidate_ids=candidate_ids,
        )
