"""Helpers for retrieving typical plant canopy area."""
from __future__ import annotations

from typing import Dict

from .utils import load_dataset, normalize_key, list_dataset_entries

DATA_FILE = "canopy_area_guidelines.json"

_DATA: Dict[str, float] = load_dataset(DATA_FILE)

__all__ = ["list_supported_plants", "get_default_canopy_area"]


def list_supported_plants() -> list[str]:
    """Return plant types with canopy area data."""
    return list_dataset_entries(_DATA)


def get_default_canopy_area(plant_type: str) -> float:
    """Return typical canopy area (m²) for ``plant_type`` or 0.25."""
    area = _DATA.get(normalize_key(plant_type))
    try:
        return float(area) if area is not None else 0.25
    except (TypeError, ValueError):
        return 0.25
