from typing import cast

from pytest import MonkeyPatch

import putonghua.providers.anki_connect as anki_connect
from putonghua.anki.connectivity import AnkiConnectivityResult, check_anki_connect


class _FakeResponse:
    def __init__(self, payload: object) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> object:
        return self._payload


class _FakeClient:
    def __init__(self, responses: list[object]) -> None:
        self._responses = responses
        self.calls: list[tuple[str, dict[str, object], dict[str, str]]] = []

    def __enter__(self) -> "_FakeClient":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        return None

    def post(
        self,
        url: str,
        *,
        json: dict[str, object],
        headers: dict[str, str],
    ) -> _FakeResponse:
        self.calls.append((url, json, headers))
        return _FakeResponse(self._responses.pop(0))


def _build_fake_client(timeout: float, fake_client: _FakeClient) -> _FakeClient:
    del timeout
    return fake_client


def test_check_anki_connect_returns_version_and_decks(
    monkeypatch: MonkeyPatch,
) -> None:
    fake_client = _FakeClient(
        responses=[
            {"result": 6, "error": None},
            {"result": ["Mandarin", "Default"], "error": None},
        ]
    )

    def _fake_httpx_client(timeout: float) -> _FakeClient:
        return _build_fake_client(timeout, fake_client)

    monkeypatch.setattr(anki_connect.httpx, "Client", _fake_httpx_client)

    result = check_anki_connect(
        base_url="http://127.0.0.1:8765",
        timeout_seconds=5.0,
        api_key=None,
    )

    assert result == AnkiConnectivityResult(
        version=6,
        deck_names=["Default", "Mandarin"],
        base_url="http://127.0.0.1:8765",
    )


def test_check_anki_connect_raises_on_action_error(monkeypatch: MonkeyPatch) -> None:
    fake_client = _FakeClient(
        responses=[
            {"result": None, "error": "valid api key must be provided"},
        ]
    )

    def _fake_httpx_client(timeout: float) -> _FakeClient:
        return _build_fake_client(timeout, fake_client)

    monkeypatch.setattr(anki_connect.httpx, "Client", _fake_httpx_client)

    try:
        check_anki_connect(
            base_url="http://127.0.0.1:8765",
            timeout_seconds=5.0,
            api_key=None,
        )
    except ValueError as exc:
        assert "valid api key" in str(exc)
    else:
        raise AssertionError("Expected ValueError for failed AnkiConnect action")


def test_list_note_types_and_get_note_type(monkeypatch: MonkeyPatch) -> None:
    fake_client = _FakeClient(
        responses=[
            {"result": ["Putonghua V1", "Basic"], "error": None},
            {"result": ["Simplified", "Pinyin", "English"], "error": None},
            {
                "result": {
                    "Recognition": {
                        "Front": "{{Simplified}}",
                        "Back": "{{Pinyin}}<hr>{{English}}",
                    },
                    "Production": {
                        "Front": "{{English}}",
                        "Back": "{{Simplified}}",
                    },
                },
                "error": None,
            },
        ]
    )

    def _fake_httpx_client(timeout: float) -> _FakeClient:
        return _build_fake_client(timeout, fake_client)

    monkeypatch.setattr(anki_connect.httpx, "Client", _fake_httpx_client)

    provider = anki_connect.AnkiConnectProvider(
        anki_connect.AnkiConnectConfig(
            base_url="http://127.0.0.1:8765",
            timeout_seconds=5.0,
            api_key=None,
        )
    )

    assert provider.list_note_types() == ["Basic", "Putonghua V1"]

    note_type = provider.get_note_type("Putonghua V1")
    assert note_type.name == "Putonghua V1"
    assert [field.name for field in note_type.fields] == [
        "Simplified",
        "Pinyin",
        "English",
    ]
    assert [template.name for template in note_type.card_templates] == [
        "Recognition",
        "Production",
    ]


def test_publish_note_sends_expected_add_note_payload(
    monkeypatch: MonkeyPatch,
) -> None:
    fake_client = _FakeClient(
        responses=[
            {"result": 42001, "error": None},
        ]
    )

    def _fake_httpx_client(timeout: float) -> _FakeClient:
        return _build_fake_client(timeout, fake_client)

    monkeypatch.setattr(anki_connect.httpx, "Client", _fake_httpx_client)

    provider = anki_connect.AnkiConnectProvider(
        anki_connect.AnkiConnectConfig(
            base_url="http://127.0.0.1:8765",
            timeout_seconds=5.0,
            api_key=None,
        )
    )
    result = provider.publish_note(
        anki_connect.AnkiPublishNoteRequest(
            deck_name="Mandarin",
            note_type_name="Mandarin vocab",
            fields={
                "Hanzi": "你好",
                "Pinyin": "ni3 hao3",
                "English": "hello",
                "Audio": "",
            },
            tags=["putonghua-test"],
        )
    )

    assert result.note_id == 42001
    assert len(fake_client.calls) == 1
    _, payload, _ = fake_client.calls[0]
    assert payload["action"] == "addNote"
    params = cast(dict[str, object], payload["params"])
    note = cast(dict[str, object], params["note"])
    assert note["deckName"] == "Mandarin"
    assert note["modelName"] == "Mandarin vocab"
    fields = cast(dict[str, object], note["fields"])
    assert fields["Hanzi"] == "你好"
    assert note["tags"] == ["putonghua-test"]
    options = cast(dict[str, object], note["options"])
    assert options["allowDuplicate"] is False
