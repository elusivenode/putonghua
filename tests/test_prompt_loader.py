from putonghua.prompts.loader import load_prompt


def test_load_prompt_reads_versioned_asset() -> None:
    prompt = load_prompt("extraction/mixed_candidates_v1.md")

    assert "Mandarin flashcard candidates" in prompt
