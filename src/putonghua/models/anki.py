"""Anki discovery models."""

from dataclasses import dataclass


@dataclass(frozen=True)
class AnkiConnectivityResult:
    """Validated AnkiConnect capability snapshot."""

    version: int
    deck_names: list[str]
    base_url: str


@dataclass(frozen=True)
class AnkiNoteField:
    """One ordered note-type field."""

    name: str
    order: int


@dataclass(frozen=True)
class AnkiCardTemplate:
    """One card template attached to a note type."""

    name: str
    front_template: str
    back_template: str


@dataclass(frozen=True)
class AnkiNoteTypeView:
    """Described Anki note type."""

    name: str
    fields: list[AnkiNoteField]
    card_templates: list[AnkiCardTemplate]


@dataclass(frozen=True)
class AnkiPublishNoteRequest:
    """Minimal note payload for one Anki publish call."""

    deck_name: str
    note_type_name: str
    fields: dict[str, str]
    tags: list[str]


@dataclass(frozen=True)
class AnkiPublishNoteResult:
    """Result of creating one Anki note."""

    note_id: int
