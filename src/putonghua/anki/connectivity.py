"""Compatibility wrapper for AnkiConnect connectivity checks."""

from putonghua.models.anki import AnkiConnectivityResult
from putonghua.providers.anki_connect import AnkiConnectConfig, AnkiConnectProvider


def check_anki_connect(
    *,
    base_url: str,
    timeout_seconds: float,
    api_key: str | None = None,
) -> AnkiConnectivityResult:
    """Verify that AnkiConnect is reachable and can read deck names."""

    provider = AnkiConnectProvider(
        AnkiConnectConfig(
            base_url=base_url,
            timeout_seconds=timeout_seconds,
            api_key=api_key,
        )
    )
    return provider.check_connectivity()
