"""Helpers for accessing the plant registry."""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any, Dict, Optional

try:
    from homeassistant.core import HomeAssistant
except ModuleNotFoundError:  # pragma: no cover - tests run without HA
    HomeAssistant = None  # type: ignore

from .json_io import load_json
from custom_components.horticulture_assistant.utils.path_utils import config_path

PLANT_REGISTRY_FILE = "data/local/plants/plant_registry.json"


@lru_cache(maxsize=None)
def _load_registry(path: str) -> Dict[str, Any]:
    """Load and cache the plant registry JSON at ``path``."""
    try:
        return load_json(path)
    except Exception:
        return {}


def get_plant_metadata(plant_id: str, hass: HomeAssistant | None = None) -> Dict[str, Any]:
    """Return metadata for ``plant_id`` from the plant registry."""
    reg_path = config_path(hass, PLANT_REGISTRY_FILE)
    data = _load_registry(reg_path)
    return data.get(plant_id, {})


def get_plant_type(plant_id: str, hass: HomeAssistant | None = None) -> Optional[str]:
    """Return the plant type for ``plant_id`` if available."""
    meta = get_plant_metadata(plant_id, hass)
    ptype = meta.get("plant_type")
    return str(ptype) if ptype else None

__all__ = ["PLANT_REGISTRY_FILE", "get_plant_metadata", "get_plant_type"]
