"""Chunk-level review chat workflow."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from putonghua.database.connection import connect
from putonghua.database.migrations import migrate_database
from putonghua.database.repositories import (
    CandidateCardCreateRecord,
    CandidateRepository,
    ReviewConversationRepository,
    ReviewConversationRow,
    ReviewMessageRow,
    ReviewSuggestionCreateRecord,
    ReviewSuggestionRepository,
    ReviewSuggestionRow,
    SourceRepository,
    StudyChunkRepository,
)
from putonghua.models.candidates import CandidateCardView, parse_candidate_type
from putonghua.models.chunks import StudyChunkView
from putonghua.models.review import (
    ChunkChatResult,
    ChunkReviewResponse,
    ReviewConversationView,
    ReviewMessageView,
    ReviewSuggestionView,
)


class ChunkReviewProvider(Protocol):
    """Provider interface for chunk-level review chat."""

    prompt_version: str

    def chat(
        self,
        *,
        chunk: StudyChunkView,
        candidates: list[CandidateCardView],
        messages: list[ReviewMessageView],
    ) -> ChunkReviewResponse:
        """Answer one chunk review request."""
        ...


@dataclass(frozen=True)
class ChunkReviewService:
    """Coordinate persisted chunk context with a review chat provider."""

    database_path: Path
    provider: ChunkReviewProvider
    provider_name: str
    model_name: str

    def start_or_resume_chunk_conversation(
        self, chunk_id: str
    ) -> ReviewConversationView:
        """Return the latest conversation for a chunk or create one."""

        migrate_database(self.database_path)
        with connect(self.database_path) as connection:
            chunk_repository = StudyChunkRepository(connection)
            conversation_repository = ReviewConversationRepository(connection)
            chunk = chunk_repository.get_chunk(chunk_id)
            if chunk is None:
                message = f"No study chunk found for id {chunk_id}"
                raise ValueError(message)

            conversation = conversation_repository.get_latest_for_chunk(chunk_id)
            if conversation is None:
                conversation_id = conversation_repository.create_conversation(
                    study_chunk_id=chunk_id,
                    provider=self.provider_name,
                    model=self.model_name,
                    prompt_version=self.provider.prompt_version,
                )
                conversation = ReviewConversationRow(
                    id=conversation_id,
                    study_chunk_id=chunk_id,
                    provider=self.provider_name,
                    model=self.model_name,
                    prompt_version=self.provider.prompt_version,
                )

        return _conversation_view(conversation)

    def chat_for_chunk(self, chunk_id: str, prompt: str) -> ChunkChatResult:
        """Persist one user prompt and provider response for a chunk."""

        migrate_database(self.database_path)
        with connect(self.database_path) as connection:
            chunk_repository = StudyChunkRepository(connection)
            candidate_repository = CandidateRepository(connection)
            conversation_repository = ReviewConversationRepository(connection)
            suggestion_repository = ReviewSuggestionRepository(connection)
            source_repository = SourceRepository(connection)

            chunk_row = chunk_repository.get_chunk(chunk_id)
            if chunk_row is None:
                message = f"No study chunk found for id {chunk_id}"
                raise ValueError(message)
            conversation = conversation_repository.get_latest_for_chunk(chunk_id)
            if conversation is None:
                conversation_id = conversation_repository.create_conversation(
                    study_chunk_id=chunk_id,
                    provider=self.provider_name,
                    model=self.model_name,
                    prompt_version=self.provider.prompt_version,
                )
                conversation = ReviewConversationRow(
                    id=conversation_id,
                    study_chunk_id=chunk_id,
                    provider=self.provider_name,
                    model=self.model_name,
                    prompt_version=self.provider.prompt_version,
                )

            conversation_repository.add_message(conversation.id, "user", prompt)
            messages = [
                _message_view(message)
                for message in conversation_repository.list_messages(conversation.id)
            ]
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
                for row in candidate_repository.list_candidates_for_chunk(chunk_id)
            ]
            response = self.provider.chat(
                chunk=chunk,
                candidates=candidates,
                messages=messages,
            )
            assistant_message_id = conversation_repository.add_message(
                conversation.id,
                "assistant",
                response.assistant_text,
            )
            source = source_repository.get_source_context(chunk.source_id)
            if source is None:
                message = f"No source found for chunk {chunk_id}"
                raise ValueError(message)
            candidate_repository.create_candidates(
                [
                    CandidateCardCreateRecord(
                        project_id=source.project_id,
                        source_id=source.id,
                        study_chunk_id=chunk_id,
                        candidate_type=card.candidate_type,
                        simplified=card.simplified,
                        traditional=card.traditional,
                        pinyin=card.pinyin,
                        english=card.english,
                        provenance={
                            "origin": "review_chat",
                            "conversation_id": conversation.id,
                            "source_message_id": assistant_message_id,
                            "candidate_type": card.candidate_type,
                            "source_excerpt": card.source_excerpt,
                            "rationale": card.rationale,
                            "provider": conversation.provider,
                            "model": conversation.model,
                            "prompt_version": conversation.prompt_version,
                        },
                    )
                    for card in response.suggested_cards
                ]
            )
            suggestion_repository.replace_for_message(
                assistant_message_id,
                [
                    ReviewSuggestionCreateRecord(
                        conversation_id=conversation.id,
                        study_chunk_id=chunk_id,
                        source_message_id=assistant_message_id,
                        suggestion_index=index,
                        candidate_type=card.candidate_type,
                        simplified=card.simplified,
                        traditional=card.traditional,
                        pinyin=card.pinyin,
                        english=card.english,
                        rationale=card.rationale,
                        source_excerpt=card.source_excerpt,
                    )
                    for index, card in enumerate(response.suggested_cards)
                ],
            )

        return ChunkChatResult(
            conversation_id=conversation.id,
            assistant_text=response.assistant_text,
            suggested_cards=response.suggested_cards,
        )

    def list_conversation_messages(
        self,
        conversation_id: str,
    ) -> list[ReviewMessageView]:
        """Return persisted messages for one conversation."""

        migrate_database(self.database_path)
        with connect(self.database_path) as connection:
            repository = ReviewConversationRepository(connection)
            return [
                _message_view(message)
                for message in repository.list_messages(conversation_id)
            ]

    def list_review_suggestions(
        self,
        conversation_id: str,
    ) -> list[ReviewSuggestionView]:
        """Return persisted structured suggestions for one conversation."""

        migrate_database(self.database_path)
        with connect(self.database_path) as connection:
            repository = ReviewSuggestionRepository(connection)
            return [
                _suggestion_view(suggestion)
                for suggestion in repository.list_for_conversation(conversation_id)
            ]


def _conversation_view(row: ReviewConversationRow) -> ReviewConversationView:
    """Convert a repository row into a public conversation view."""

    return ReviewConversationView(
        id=row.id,
        study_chunk_id=row.study_chunk_id,
        provider=row.provider,
        model=row.model,
        prompt_version=row.prompt_version,
    )


def _message_view(row: ReviewMessageRow) -> ReviewMessageView:
    """Convert a repository row into a public message view."""

    return ReviewMessageView(
        id=row.id,
        conversation_id=row.conversation_id,
        role=row.role,
        content=row.content,
    )


def _suggestion_view(
    row: ReviewSuggestionRow,
) -> ReviewSuggestionView:
    """Convert a repository row into a public suggestion view."""

    return ReviewSuggestionView(
        id=row.id,
        conversation_id=row.conversation_id,
        study_chunk_id=row.study_chunk_id,
        source_message_id=row.source_message_id,
        suggestion_index=row.suggestion_index,
        candidate_type=row.candidate_type,
        simplified=row.simplified,
        traditional=row.traditional,
        pinyin=row.pinyin,
        english=row.english,
        rationale=row.rationale,
        source_excerpt=row.source_excerpt,
        status=row.status,
        promoted_candidate_card_id=row.promoted_candidate_card_id,
    )
