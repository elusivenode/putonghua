"""Stored review suggestion listing and promotion workflow."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from putonghua.database.connection import connect
from putonghua.database.migrations import migrate_database
from putonghua.database.repositories import (
    CandidateCardCreateRecord,
    CandidateRepository,
    ReviewConversationRepository,
    ReviewSuggestionRepository,
    SourceRepository,
    StudyChunkRepository,
)
from putonghua.models.candidates import CandidatePromotionResult
from putonghua.models.review import ReviewSuggestionView


@dataclass(frozen=True)
class ReviewSuggestionService:
    """List and promote persisted review suggestions."""

    database_path: Path

    def list_review_suggestions(
        self,
        conversation_id: str,
    ) -> list[ReviewSuggestionView]:
        """Return persisted structured suggestions for one conversation."""

        migrate_database(self.database_path)
        with connect(self.database_path) as connection:
            repository = ReviewSuggestionRepository(connection)
            suggestions = repository.list_for_conversation(conversation_id)

        return [
            ReviewSuggestionView(
                id=suggestion.id,
                conversation_id=suggestion.conversation_id,
                study_chunk_id=suggestion.study_chunk_id,
                source_message_id=suggestion.source_message_id,
                suggestion_index=suggestion.suggestion_index,
                candidate_type=suggestion.candidate_type,
                simplified=suggestion.simplified,
                traditional=suggestion.traditional,
                pinyin=suggestion.pinyin,
                english=suggestion.english,
                rationale=suggestion.rationale,
                source_excerpt=suggestion.source_excerpt,
                status=suggestion.status,
                promoted_candidate_card_id=suggestion.promoted_candidate_card_id,
            )
            for suggestion in suggestions
        ]

    def promote_suggestion(self, suggestion_id: str) -> CandidatePromotionResult:
        """Promote one stored suggestion into a durable candidate card."""

        migrate_database(self.database_path)
        with connect(self.database_path) as connection:
            suggestion_repository = ReviewSuggestionRepository(connection)
            candidate_repository = CandidateRepository(connection)
            chunk_repository = StudyChunkRepository(connection)
            source_repository = SourceRepository(connection)
            conversation_repository = ReviewConversationRepository(connection)

            suggestion = suggestion_repository.get_suggestion(suggestion_id)
            if suggestion is None:
                message = f"No review suggestion found for id {suggestion_id}"
                raise ValueError(message)

            if suggestion.promoted_candidate_card_id is not None:
                existing = candidate_repository.get_candidate(
                    suggestion.promoted_candidate_card_id
                )
                if existing is None:
                    message = (
                        "Review suggestion references a missing promoted candidate: "
                        f"{suggestion.promoted_candidate_card_id}"
                    )
                    raise ValueError(message)
                return CandidatePromotionResult(
                    suggestion_id=suggestion_id,
                    candidate_id=existing.id,
                    status=existing.status,
                    created=False,
                )

            chunk = chunk_repository.get_chunk(suggestion.study_chunk_id)
            if chunk is None:
                message = f"No study chunk found for id {suggestion.study_chunk_id}"
                raise ValueError(message)

            source = source_repository.get_source_context(chunk.source_id)
            if source is None:
                message = f"No source found for chunk {chunk.id}"
                raise ValueError(message)

            conversation = conversation_repository.get_conversation(
                suggestion.conversation_id
            )
            if conversation is None:
                message = (
                    "No review conversation found for suggestion "
                    f"{suggestion_id}: {suggestion.conversation_id}"
                )
                raise ValueError(message)

            candidate_id = candidate_repository.create_candidates(
                [
                    CandidateCardCreateRecord(
                        project_id=source.project_id,
                        source_id=source.id,
                        study_chunk_id=chunk.id,
                        candidate_type=suggestion.candidate_type,
                        simplified=suggestion.simplified,
                        traditional=suggestion.traditional,
                        pinyin=suggestion.pinyin,
                        english=suggestion.english,
                        provenance={
                            "origin": "review_suggestion",
                            "conversation_id": suggestion.conversation_id,
                            "review_suggestion_id": suggestion.id,
                            "study_chunk_id": suggestion.study_chunk_id,
                            "source_message_id": suggestion.source_message_id,
                            "suggestion_index": suggestion.suggestion_index,
                            "candidate_type": suggestion.candidate_type,
                            "source_excerpt": suggestion.source_excerpt,
                            "rationale": suggestion.rationale,
                            "provider": conversation.provider,
                            "model": conversation.model,
                            "prompt_version": conversation.prompt_version,
                        },
                        status="promoted",
                    )
                ]
            )[0]
            suggestion_repository.mark_promoted(suggestion.id, candidate_id)

        return CandidatePromotionResult(
            suggestion_id=suggestion_id,
            candidate_id=candidate_id,
            status="promoted",
            created=True,
        )
