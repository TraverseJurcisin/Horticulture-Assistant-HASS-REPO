"""Lookup helpers for stage-specific fertigation recipes."""
from __future__ import annotations

from typing import Dict

from .utils import load_dataset, normalize_key

DATA_FILE = "fertigation_recipes.json"
_DATA: Dict[str, Dict[str, Dict[str, float]]] = load_dataset(DATA_FILE)

__all__ = ["list_supported_plants", "get_recipe"]


def list_supported_plants() -> list[str]:
    """Return plant types with fertigation recipes."""
    return sorted(_DATA.keys())


def get_recipe(plant_type: str, stage: str) -> Dict[str, float]:
    """Return grams per liter of fertilizer for the plant stage.

    Unknown plants or stages return an empty dictionary.
    """
    plant = _DATA.get(normalize_key(plant_type))
    if not plant:
        return {}
    return plant.get(normalize_key(stage), {})
