"""AnkiConnect provider adapter."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypedDict, cast

import httpx

from putonghua.models.anki import (
    AnkiCardTemplate,
    AnkiConnectivityResult,
    AnkiNoteField,
    AnkiNoteTypeView,
    AnkiPublishNoteRequest,
    AnkiPublishNoteResult,
)


class _AnkiResponse(TypedDict):
    """Minimal AnkiConnect response envelope."""

    result: object
    error: object | None


@dataclass(frozen=True)
class AnkiConnectConfig:
    """Connection settings for a local AnkiConnect endpoint."""

    base_url: str
    timeout_seconds: float
    api_key: str | None = None


class AnkiConnectProvider:
    """Read discovery data from a local AnkiConnect endpoint."""

    def __init__(self, config: AnkiConnectConfig) -> None:
        self._config = config

    def check_connectivity(self) -> AnkiConnectivityResult:
        """Verify that AnkiConnect is reachable and can read deck names."""

        with httpx.Client(timeout=self._config.timeout_seconds) as client:
            version = self._invoke_action(client=client, action="version")
            deck_names = self._invoke_action(client=client, action="deckNames")

        if not isinstance(version, int):
            message = "AnkiConnect returned a non-integer version."
            raise ValueError(message)

        typed_deck_names = _parse_string_list(
            deck_names,
            message="AnkiConnect returned invalid deck names.",
        )
        return AnkiConnectivityResult(
            version=version,
            deck_names=sorted(typed_deck_names),
            base_url=self._config.base_url,
        )

    def list_decks(self) -> list[str]:
        """Return available deck names."""

        with httpx.Client(timeout=self._config.timeout_seconds) as client:
            deck_names = self._invoke_action(client=client, action="deckNames")
        return sorted(
            _parse_string_list(
                deck_names,
                message="AnkiConnect returned invalid deck names.",
            )
        )

    def list_note_types(self) -> list[str]:
        """Return available note type names."""

        with httpx.Client(timeout=self._config.timeout_seconds) as client:
            note_types = self._invoke_action(client=client, action="modelNames")
        return sorted(
            _parse_string_list(
                note_types,
                message="AnkiConnect returned invalid note type names.",
            )
        )

    def get_note_type(self, note_type_name: str) -> AnkiNoteTypeView:
        """Describe one note type, including ordered fields and templates."""

        with httpx.Client(timeout=self._config.timeout_seconds) as client:
            field_names = self._invoke_action(
                client=client,
                action="modelFieldNames",
                params={"modelName": note_type_name},
            )
            raw_templates = self._invoke_action(
                client=client,
                action="modelTemplates",
                params={"modelName": note_type_name},
            )

        typed_field_names = _parse_string_list(
            field_names,
            message="AnkiConnect returned invalid note type field names.",
        )
        typed_templates = _parse_templates(raw_templates)

        return AnkiNoteTypeView(
            name=note_type_name,
            fields=[
                AnkiNoteField(name=field_name, order=index)
                for index, field_name in enumerate(typed_field_names)
            ],
            card_templates=typed_templates,
        )

    def publish_note(self, request: AnkiPublishNoteRequest) -> AnkiPublishNoteResult:
        """Create one note in Anki."""

        with httpx.Client(timeout=self._config.timeout_seconds) as client:
            note_id = self._invoke_action(
                client=client,
                action="addNote",
                params={
                    "note": {
                        "deckName": request.deck_name,
                        "modelName": request.note_type_name,
                        "fields": request.fields,
                        "tags": request.tags,
                        "options": {"allowDuplicate": False},
                    }
                },
            )

        if not isinstance(note_id, int):
            message = "AnkiConnect returned a non-integer note id."
            raise ValueError(message)

        return AnkiPublishNoteResult(note_id=note_id)

    def _invoke_action(
        self,
        *,
        client: httpx.Client,
        action: str,
        params: dict[str, object] | None = None,
    ) -> object:
        """Execute a single AnkiConnect action."""

        payload: dict[str, object] = {
            "action": action,
            "version": 6,
        }
        if self._config.api_key is not None:
            payload["key"] = self._config.api_key
        if params is not None:
            payload["params"] = params

        response = client.post(
            self._config.base_url,
            json=payload,
            headers={"Content-Type": "application/json"},
        )
        response.raise_for_status()
        body = response.json()

        if not isinstance(body, dict):
            message = "AnkiConnect returned a non-object response."
            raise ValueError(message)

        typed_body = cast(_AnkiResponse, body)
        error = typed_body["error"]
        if error is not None:
            message = f"AnkiConnect action {action!r} failed: {error}"
            raise ValueError(message)

        return typed_body["result"]


def _parse_string_list(value: object, *, message: str) -> list[str]:
    """Validate a list of strings from AnkiConnect."""

    if not isinstance(value, list):
        raise ValueError(message)

    typed_value = cast(list[object], value)
    if not all(isinstance(item, str) for item in typed_value):
        raise ValueError(message)

    return cast(list[str], typed_value)


def _parse_templates(value: object) -> list[AnkiCardTemplate]:
    """Validate note-type template data from AnkiConnect."""

    if not isinstance(value, dict):
        message = "AnkiConnect returned invalid note type templates."
        raise ValueError(message)

    templates: list[AnkiCardTemplate] = []
    for name, raw_template in cast(dict[object, object], value).items():
        if not isinstance(name, str) or not isinstance(raw_template, dict):
            message = "AnkiConnect returned invalid note type templates."
            raise ValueError(message)
        typed_template = cast(dict[str, object], raw_template)
        front = typed_template.get("Front")
        back = typed_template.get("Back")
        if not isinstance(front, str) or not isinstance(back, str):
            message = "AnkiConnect returned invalid note type templates."
            raise ValueError(message)
        templates.append(
            AnkiCardTemplate(
                name=name,
                front_template=front,
                back_template=back,
            )
        )

    return templates
