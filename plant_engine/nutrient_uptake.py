"""Lookup daily nutrient uptake targets by plant type and stage."""
from __future__ import annotations

from typing import Dict

from .utils import load_dataset

DATA_FILE = "nutrient_uptake.json"

_DATA: Dict[str, Dict[str, Dict[str, float]]] = load_dataset(DATA_FILE)

__all__ = ["list_supported_plants", "get_daily_uptake"]


def list_supported_plants() -> list[str]:
    """Return all plant types with uptake data."""
    return sorted(_DATA.keys())


def get_daily_uptake(plant_type: str, stage: str) -> Dict[str, float]:
    """Return mg/day uptake for ``plant_type`` and ``stage``."""
    plant = _DATA.get(plant_type.lower())
    if not plant:
        return {}
    return plant.get(stage.lower(), {})
