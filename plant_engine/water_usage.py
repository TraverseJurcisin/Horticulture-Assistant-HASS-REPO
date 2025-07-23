"""Lookup daily water use estimates for irrigation planning."""
from __future__ import annotations

from typing import Dict

from .utils import load_dataset, normalize_key, list_dataset_entries

DATA_FILE = "water_usage_guidelines.json"

_DATA: Dict[str, Dict[str, float]] = load_dataset(DATA_FILE)

__all__ = ["list_supported_plants", "get_daily_use"]


def list_supported_plants() -> list[str]:
    """Return all plant types with water use data."""
    return list_dataset_entries(_DATA)


def get_daily_use(plant_type: str, stage: str) -> float:
    """Return daily water usage in milliliters for a plant stage."""
    plant = _DATA.get(normalize_key(plant_type))
    if not plant:
        return 0.0
    try:
        return float(plant.get(normalize_key(stage), 0.0))
    except (TypeError, ValueError):
        return 0.0
