from putonghua.models.anki import (
    AnkiCardTemplate,
    AnkiConnectivityResult,
    AnkiNoteField,
    AnkiNoteTypeView,
)
from putonghua.services.anki_discovery import AnkiDiscoveryService


class _FakeAnkiProvider:
    def check_connectivity(self) -> AnkiConnectivityResult:
        return AnkiConnectivityResult(
            version=6,
            deck_names=["Default", "Mandarin"],
            base_url="http://127.0.0.1:8765",
        )

    def list_decks(self) -> list[str]:
        return ["Default", "Mandarin"]

    def list_note_types(self) -> list[str]:
        return ["Basic", "Putonghua V1"]

    def get_note_type(self, note_type_name: str) -> AnkiNoteTypeView:
        assert note_type_name == "Putonghua V1"
        return AnkiNoteTypeView(
            name=note_type_name,
            fields=[
                AnkiNoteField(name="Simplified", order=0),
                AnkiNoteField(name="Pinyin", order=1),
            ],
            card_templates=[
                AnkiCardTemplate(
                    name="Recognition",
                    front_template="{{Simplified}}",
                    back_template="{{Pinyin}}",
                )
            ],
        )


def test_anki_discovery_service_proxies_provider_calls() -> None:
    service = AnkiDiscoveryService(provider=_FakeAnkiProvider())

    assert service.check_connectivity().version == 6
    assert service.list_decks() == ["Default", "Mandarin"]
    assert service.list_note_types() == ["Basic", "Putonghua V1"]

    note_type = service.describe_note_type("Putonghua V1")
    assert note_type.name == "Putonghua V1"
    assert [field.name for field in note_type.fields] == ["Simplified", "Pinyin"]
    assert [template.name for template in note_type.card_templates] == ["Recognition"]
