"""Shared test helpers."""

from putonghua.models.candidates import CandidateDraft
from putonghua.models.review import ChunkReviewResponse


class FakeReviewProvider:
    """Deterministic review provider for service tests."""

    prompt_version = "review/chunk_chat_v1.md"

    def chat(self, **kwargs: object) -> ChunkReviewResponse:
        messages = kwargs["messages"]
        assert isinstance(messages, list)
        return ChunkReviewResponse(
            assistant_text="Focus on the phrase and one full sentence.",
            suggested_cards=[
                CandidateDraft(
                    candidate_type="sentence",
                    simplified="我会尽量地把每一个字都说出来。",
                    traditional="我會盡量地把每一個字都說出來。",
                    pinyin="wǒ huì jǐn liàng de bǎ měi yí gè zì dōu shuō chū lái",
                    english="I will try my best to pronounce every word clearly.",
                    rationale="Good full-sentence listening support card.",
                    source_excerpt="我会尽量地把每一个字都说出来",
                )
            ],
        )
