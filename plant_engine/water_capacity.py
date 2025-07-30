"""Soil water holding capacity calculations."""
from __future__ import annotations

from typing import Dict

from .utils import load_dataset, normalize_key, list_dataset_entries

DATA_FILE = "soil/soil_water_capacity.json"

_DATA: Dict[str, float] = load_dataset(DATA_FILE)

__all__ = [
    "list_supported_textures",
    "get_capacity",
    "estimate_storage",
]


def list_supported_textures() -> list[str]:
    """Return soil textures with water capacity data."""
    return list_dataset_entries(_DATA)


def get_capacity(texture: str) -> float:
    """Return water holding capacity (mm per 30 cm) for ``texture``."""
    value = _DATA.get(normalize_key(texture))
    return float(value) if isinstance(value, (int, float)) else 0.0


def estimate_storage(texture: str, depth_cm: float) -> float:
    """Return water storage (mm) for ``depth_cm`` of ``texture`` soil."""
    if depth_cm <= 0:
        raise ValueError("depth_cm must be positive")
    capacity = get_capacity(texture)
    if capacity <= 0:
        return 0.0
    return round(capacity * (depth_cm / 30.0), 2)
