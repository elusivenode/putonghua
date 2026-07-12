from pathlib import Path

import pytest

from putonghua.config.loader import load_settings


def test_load_settings_expands_relative_paths(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "\n".join(
            [
                "app:",
                "  data_dir: .local/share/putonghua",
                "  database_path: .local/share/putonghua/putonghua.db",
                "  log_level: DEBUG",
            ]
        ),
        encoding="utf-8",
    )

    settings = load_settings(config_path)

    assert settings.app.data_dir == tmp_path / ".local/share/putonghua"
    assert (
        settings.app.database_path == tmp_path / ".local/share/putonghua/putonghua.db"
    )
    assert settings.app.log_level == "DEBUG"


def test_load_settings_requires_existing_file(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_settings(tmp_path / "missing.yaml")
