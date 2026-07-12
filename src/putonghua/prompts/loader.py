"""Versioned prompt asset loading."""

from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parent


def load_prompt(relative_path: str) -> str:
    """Load one prompt asset relative to the prompts package."""

    prompt_path = PROMPTS_DIR / relative_path
    if not prompt_path.exists():
        message = f"Prompt asset not found: {relative_path}"
        raise FileNotFoundError(message)
    return prompt_path.read_text(encoding="utf-8").strip()
