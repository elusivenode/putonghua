"""Tutorial session models."""

from dataclasses import dataclass

TutorialStepKey = str

TUTORIAL_STEP_ORDER: tuple[TutorialStepKey, ...] = (
    "session_layout",
    "workflow_overview",
    "chunk_selected",
    "candidates_extracted",
    "suggestion_promoted",
    "candidate_published",
)


@dataclass(frozen=True)
class TutorialStepView:
    """One tutorial milestone and its current completion state."""

    key: TutorialStepKey
    title: str
    command: str
    actions: list[str]
    choice_hint: str
    success_condition: str
    why: str
    completed: bool
    detail: str


@dataclass(frozen=True)
class TutorialSessionView:
    """Persisted tutorial session with resolved progress."""

    id: str
    status: str
    current_step: str
    project_id: str | None
    source_id: str | None
    study_chunk_id: str | None
    review_conversation_id: str | None
    review_suggestion_id: str | None
    candidate_card_id: str | None
    publication_record_id: str | None
    completed_at: str | None
    steps: list[TutorialStepView]
