"""Configuration loading helpers."""

import os
from pathlib import Path
from typing import Any, cast

import yaml

from putonghua.config.settings import Settings


def load_settings(path: Path) -> Settings:
    """Load settings from a YAML file."""

    if not path.exists():
        message = f"Configuration file not found: {path}"
        raise FileNotFoundError(message)

    with path.open("r", encoding="utf-8") as handle:
        raw_data = cast(object, yaml.safe_load(handle) or {})

    if not isinstance(raw_data, dict):
        message = f"Configuration root must be a mapping: {path}"
        raise ValueError(message)

    validated_data = cast(dict[str, Any], raw_data)
    return Settings.model_validate(_expand_paths(validated_data, path.parent))


def _expand_paths(data: dict[str, Any], base_dir: Path) -> dict[str, Any]:
    """Resolve configured paths relative to the configuration file."""

    app_data = dict(data.get("app", {}))
    for key in ("data_dir", "database_path"):
        value = app_data.get(key)
        if isinstance(value, str):
            candidate = Path(value).expanduser()
            if not candidate.is_absolute():
                app_data[key] = base_dir / candidate

    expanded = dict(data)
    expanded["app"] = app_data
    openai_data = dict(expanded.get("openai", {}))
    if openai_data.get("api_key") is None:
        env_api_key = os.getenv("OPENAI_API_KEY")
        if env_api_key:
            openai_data["api_key"] = env_api_key
    expanded["openai"] = openai_data
    return expanded
