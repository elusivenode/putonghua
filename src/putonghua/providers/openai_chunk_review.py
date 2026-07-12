"""OpenAI chunk review provider."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, cast

import httpx

from putonghua.models.candidates import (
    CandidateCardView,
    CandidateDraft,
    parse_candidate_type,
)
from putonghua.models.chunks import StudyChunkView
from putonghua.models.review import ChunkReviewResponse, ReviewMessageView
from putonghua.prompts.loader import load_prompt

_REVIEW_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "assistant_reply": {"type": "string"},
        "suggested_cards": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "candidate_type": {
                        "type": "string",
                        "enum": ["word", "phrase", "sentence"],
                    },
                    "simplified": {"type": "string"},
                    "traditional": {"type": "string"},
                    "pinyin": {"type": "string"},
                    "english": {"type": "string"},
                    "rationale": {"type": "string"},
                    "source_excerpt": {"type": "string"},
                },
                "required": [
                    "candidate_type",
                    "simplified",
                    "traditional",
                    "pinyin",
                    "english",
                    "rationale",
                    "source_excerpt",
                ],
                "additionalProperties": False,
            },
        },
    },
    "required": ["assistant_reply", "suggested_cards"],
    "additionalProperties": False,
}


@dataclass(frozen=True)
class OpenAIChunkReviewConfig:
    """OpenAI settings for chunk review chat."""

    api_key: str
    model: str
    timeout_seconds: float


class OpenAIChunkReviewProvider:
    """Chunk-scoped review chat through the OpenAI Responses API."""

    prompt_version = "review/chunk_chat_v1.md"

    def __init__(self, config: OpenAIChunkReviewConfig) -> None:
        self._config = config

    def chat(
        self,
        *,
        chunk: StudyChunkView,
        candidates: list[CandidateCardView],
        messages: list[ReviewMessageView],
    ) -> ChunkReviewResponse:
        """Answer one learner question about a chunk and candidate set."""

        chunk_context = _render_chunk_context(chunk, candidates)
        input_messages: list[dict[str, object]] = [
            {
                "role": "system",
                "content": [
                    {
                        "type": "input_text",
                        "text": load_prompt(self.prompt_version),
                    }
                ],
            },
            {
                "role": "user",
                "content": [{"type": "input_text", "text": chunk_context}],
            },
        ]
        for message in messages:
            input_messages.append(
                {
                    "role": message.role,
                    "content": [{"type": "input_text", "text": message.content}],
                }
            )

        payload = {
            "model": self._config.model,
            "input": input_messages,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "chunk_review",
                    "schema": _REVIEW_SCHEMA,
                    "strict": True,
                }
            },
        }

        with httpx.Client(timeout=self._config.timeout_seconds) as client:
            response = client.post(
                "https://api.openai.com/v1/responses",
                headers={
                    "Authorization": f"Bearer {self._config.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            response.raise_for_status()

        body = cast(dict[str, Any], response.json())
        output_text = _extract_output_text(body)
        try:
            parsed = cast(dict[str, object], json.loads(output_text))
        except json.JSONDecodeError as exc:
            message = "OpenAI chunk review returned invalid JSON."
            raise ValueError(message) from exc

        assistant_reply = parsed.get("assistant_reply")
        if not isinstance(assistant_reply, str):
            message = "OpenAI chunk review response missed assistant_reply."
            raise ValueError(message)

        raw_cards = parsed.get("suggested_cards")
        if not isinstance(raw_cards, list):
            message = "OpenAI chunk review response missed suggested_cards."
            raise ValueError(message)

        suggested_cards: list[CandidateDraft] = []
        for item in cast(list[object], raw_cards):
            if not isinstance(item, dict):
                continue
            candidate = _parse_candidate(cast(dict[str, object], item))
            if candidate is not None:
                suggested_cards.append(candidate)

        return ChunkReviewResponse(
            assistant_text=assistant_reply.strip(),
            suggested_cards=suggested_cards,
        )


def _render_chunk_context(
    chunk: StudyChunkView,
    candidates: list[CandidateCardView],
) -> str:
    """Render chunk and candidate context for the review model."""

    lines = [
        f"Chunk id: {chunk.id}",
        f"Chunk index: {chunk.chunk_index}",
        f"Time range: {chunk.start_seconds:.2f}-{chunk.end_seconds:.2f} seconds",
        "",
        "Transcript chunk:",
        chunk.text,
        "",
        "Existing extracted candidates:",
    ]
    if not candidates:
        lines.append("(none)")
    else:
        for candidate in candidates:
            lines.append(
                f"- {candidate.candidate_type}: "
                f"{candidate.simplified or ''} | {candidate.pinyin or ''} | "
                f"{candidate.english or ''}"
            )
    return "\n".join(lines)


def _get_required_str(record: dict[str, object], key: str) -> str | None:
    """Return a string field from a structured record if present."""

    value = record.get(key)
    if isinstance(value, str):
        return value
    return None


def _parse_candidate(record: dict[str, object]) -> CandidateDraft | None:
    """Convert one structured card suggestion into a candidate draft."""

    candidate_type = _get_required_str(record, "candidate_type")
    simplified = _get_required_str(record, "simplified")
    traditional = _get_required_str(record, "traditional")
    pinyin = _get_required_str(record, "pinyin")
    english = _get_required_str(record, "english")
    rationale = _get_required_str(record, "rationale")
    source_excerpt = _get_required_str(record, "source_excerpt")
    typed_candidate_type = (
        parse_candidate_type(candidate_type) if candidate_type is not None else None
    )
    if (
        typed_candidate_type is None
        or simplified is None
        or traditional is None
        or pinyin is None
        or english is None
        or rationale is None
        or source_excerpt is None
    ):
        return None
    return CandidateDraft(
        candidate_type=typed_candidate_type,
        simplified=simplified.strip(),
        traditional=traditional.strip(),
        pinyin=pinyin.strip(),
        english=english.strip(),
        rationale=rationale.strip(),
        source_excerpt=source_excerpt.strip(),
    )


def _extract_output_text(body: dict[str, Any]) -> str:
    """Read assistant output text from a raw Responses API payload."""

    direct_output = body.get("output_text")
    if isinstance(direct_output, str):
        return direct_output

    raw_output = body.get("output")
    if not isinstance(raw_output, list):
        message = "OpenAI chunk review did not include output content."
        raise ValueError(message)

    for item in cast(list[object], raw_output):
        if not isinstance(item, dict):
            continue
        output_item = cast(dict[str, object], item)
        content = output_item.get("content")
        if not isinstance(content, list):
            continue
        for content_item in cast(list[object], content):
            if not isinstance(content_item, dict):
                continue
            typed_content_item = cast(dict[str, object], content_item)
            if typed_content_item.get("type") != "output_text":
                continue
            text = typed_content_item.get("text")
            if isinstance(text, str):
                return text

    message = "OpenAI chunk review did not include output_text."
    raise ValueError(message)
