"""Helpers for loading and saving global integration settings."""

from __future__ import annotations

from typing import Any

from .json_io import load_json, save_json
from .path_utils import data_path

CONFIG_FILE = "horticulture_global_config.json"

DEFAULTS: dict[str, Any] = {
    "use_openai": False,
    "openai_api_key": "",
    "openai_model": "gpt-4o",
    "openai_temperature": 0.3,
    "default_threshold_mode": "profile",
}


def load_config(hass=None) -> dict[str, Any]:
    """Return the stored global configuration merged with defaults."""
    path = data_path(hass, CONFIG_FILE)
    try:
        cfg = load_json(path)
    except FileNotFoundError:
        return dict(DEFAULTS)
    except Exception:
        return dict(DEFAULTS)
    if not isinstance(cfg, dict):
        return dict(DEFAULTS)
    merged = dict(DEFAULTS)
    merged.update(cfg)
    return merged


def save_config(cfg: dict[str, Any], hass=None) -> None:
    """Persist ``cfg`` to the global config file."""
    path = data_path(hass, CONFIG_FILE)
    save_json(path, cfg)
