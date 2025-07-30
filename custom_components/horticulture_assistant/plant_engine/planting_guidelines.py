"""Lookup helpers for recommended planting depths."""
from __future__ import annotations

from typing import Dict

from .utils import load_dataset, normalize_key, list_dataset_entries

DATA_FILE = "propagation/planting_depth_guidelines.json"

# Cached dataset loaded at import time
_DATA: Dict[str, float] = load_dataset(DATA_FILE)

__all__ = ["list_supported_plants", "get_planting_depth"]


def list_supported_plants() -> list[str]:
    """Return plant types with planting depth data."""
    return list_dataset_entries(_DATA)


def get_planting_depth(plant_type: str) -> float | None:
    """Return recommended planting depth in centimeters."""
    value = _DATA.get(normalize_key(plant_type))
    return float(value) if isinstance(value, (int, float)) else None
