"""Simple utilities for silicon nutrient guidance."""

from __future__ import annotations

from typing import Dict, Mapping

from .utils import load_dataset, normalize_key, list_dataset_entries

DATA_FILE = "nutrients/silicon_guidelines.json"

_DATA: Dict[str, Dict[str, Dict[str, float]]] = load_dataset(DATA_FILE)

__all__ = [
    "list_supported_plants",
    "get_recommended_levels",
    "calculate_deficiencies",
    "calculate_surplus",
]


def list_supported_plants() -> list[str]:
    """Return plants with silicon guidelines."""
    return list_dataset_entries(_DATA)


def get_recommended_levels(plant_type: str, stage: str) -> Dict[str, float]:
    """Return recommended silicon ppm levels for a plant stage."""
    plant = _DATA.get(normalize_key(plant_type))
    if not plant:
        return {}
    return plant.get(normalize_key(stage), {})


def calculate_deficiencies(
    current_levels: Mapping[str, float],
    plant_type: str,
    stage: str,
) -> Dict[str, float]:
    """Return silicon deficit compared to guidelines."""
    target = get_recommended_levels(plant_type, stage)
    deficits: Dict[str, float] = {}
    for nutrient, rec in target.items():
        diff = round(rec - current_levels.get(nutrient, 0.0), 2)
        if diff > 0:
            deficits[nutrient] = diff
    return deficits


def calculate_surplus(
    current_levels: Mapping[str, float],
    plant_type: str,
    stage: str,
) -> Dict[str, float]:
    """Return surplus silicon ppm above recommended levels."""
    target = get_recommended_levels(plant_type, stage)
    surplus: Dict[str, float] = {}
    for nutrient, rec in target.items():
        diff = round(current_levels.get(nutrient, 0.0) - rec, 2)
        if diff > 0:
            surplus[nutrient] = diff
    return surplus
