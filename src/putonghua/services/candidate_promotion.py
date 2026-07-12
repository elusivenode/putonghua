"""Direct candidate promotion workflow."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from putonghua.database.connection import connect
from putonghua.database.migrations import migrate_database
from putonghua.database.repositories import CandidateRepository
from putonghua.models.candidates import CandidatePromotionResult


@dataclass(frozen=True)
class CandidatePromotionService:
    """Promote one extracted candidate into the publish queue."""

    database_path: Path

    def promote_candidate(self, candidate_id: str) -> CandidatePromotionResult:
        """Mark one stored extracted candidate as promoted."""

        migrate_database(self.database_path)
        with connect(self.database_path) as connection:
            repository = CandidateRepository(connection)
            candidate = repository.get_candidate(candidate_id)
            if candidate is None:
                message = f"No candidate found for id {candidate_id}"
                raise ValueError(message)

            if candidate.status in {"promoted", "published"}:
                return CandidatePromotionResult(
                    suggestion_id="",
                    candidate_id=candidate.id,
                    status=candidate.status,
                    created=False,
                )

            repository.update_status(candidate.id, "promoted")
            connection.commit()

        return CandidatePromotionResult(
            suggestion_id="",
            candidate_id=candidate_id,
            status="promoted",
            created=True,
        )
