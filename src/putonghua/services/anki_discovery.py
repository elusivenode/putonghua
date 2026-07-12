"""Anki discovery service."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from putonghua.models.anki import AnkiConnectivityResult, AnkiNoteTypeView


class AnkiDiscoveryProvider(Protocol):
    """Provider interface for Anki discovery workflows."""

    def check_connectivity(self) -> AnkiConnectivityResult:
        """Verify AnkiConnect availability and deck access."""
        ...

    def list_decks(self) -> list[str]:
        """Return available deck names."""
        ...

    def list_note_types(self) -> list[str]:
        """Return available note type names."""
        ...

    def get_note_type(self, note_type_name: str) -> AnkiNoteTypeView:
        """Describe one note type."""
        ...


@dataclass(frozen=True)
class AnkiDiscoveryService:
    """Thin service over Anki discovery provider capabilities."""

    provider: AnkiDiscoveryProvider

    def check_connectivity(self) -> AnkiConnectivityResult:
        """Return a validated connectivity snapshot."""

        return self.provider.check_connectivity()

    def list_decks(self) -> list[str]:
        """Return available deck names."""

        return self.provider.list_decks()

    def list_note_types(self) -> list[str]:
        """Return available note type names."""

        return self.provider.list_note_types()

    def describe_note_type(self, note_type_name: str) -> AnkiNoteTypeView:
        """Return one note type description."""

        return self.provider.get_note_type(note_type_name)
