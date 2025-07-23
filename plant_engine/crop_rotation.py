"""Crop rotation helper utilities."""
from __future__ import annotations

from typing import Dict, Iterable

from .utils import load_dataset, normalize_key, list_dataset_entries

DATA_FILE = "crop_rotation_guidelines.json"

_DATA: Dict[str, Dict[str, object]] = load_dataset(DATA_FILE)

__all__ = [
    "list_supported_plants",
    "get_preceding_crops",
    "get_rotation_interval",
]


def list_supported_plants() -> list[str]:
    """Return plant types with crop rotation guidelines."""
    return list_dataset_entries(_DATA)


def get_preceding_crops(plant_type: str) -> list[str]:
    """Return suitable preceding crops for ``plant_type``."""
    info = _DATA.get(normalize_key(plant_type), {})
    crops = info.get("preceding")
    if isinstance(crops, Iterable):
        return [str(c) for c in crops]
    return []


def get_rotation_interval(plant_type: str) -> int | None:
    """Return recommended months between plantings of ``plant_type``."""
    info = _DATA.get(normalize_key(plant_type), {})
    val = info.get("interval_months")
    if isinstance(val, (int, float)):
        return int(val)
    return None
