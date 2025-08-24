"""Helpers for accessing the plant registry."""

from __future__ import annotations

from functools import cache
from typing import Any

try:
    from homeassistant.core import HomeAssistant
except ModuleNotFoundError:  # pragma: no cover - tests run without HA
    HomeAssistant = None  # type: ignore

from custom_components.horticulture_assistant.utils.path_utils import config_path

from .json_io import load_json, save_json

PLANT_REGISTRY_FILE = "data/local/plants/plant_registry.json"


@cache
def _load_registry(path: str) -> dict[str, Any]:
    """Load and cache the plant registry JSON at ``path``."""
    try:
        return load_json(path)
    except Exception:
        return {}


def get_plant_metadata(plant_id: str, hass: HomeAssistant | None = None) -> dict[str, Any]:
    """Return metadata for ``plant_id`` from the plant registry."""
    reg_path = config_path(hass, PLANT_REGISTRY_FILE)
    data = _load_registry(reg_path)
    return data.get(plant_id, {})


def get_plant_type(plant_id: str, hass: HomeAssistant | None = None) -> str | None:
    """Return the plant type for ``plant_id`` if available."""
    meta = get_plant_metadata(plant_id, hass)
    ptype = meta.get("plant_type")
    return str(ptype) if ptype else None


def register_plant(
    plant_id: str, metadata: dict[str, Any], hass: HomeAssistant | None = None
) -> None:
    """Add or update ``plant_id`` in the plant registry."""
    path = config_path(hass, PLANT_REGISTRY_FILE)
    try:
        data = load_json(path)
    except Exception:
        data = {}
    data[plant_id] = metadata
    save_json(path, data)
    _load_registry.cache_clear()


__all__ = [
    "PLANT_REGISTRY_FILE",
    "get_plant_metadata",
    "get_plant_type",
    "register_plant",
]
