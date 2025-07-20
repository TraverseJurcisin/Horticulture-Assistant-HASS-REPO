"""Utility helpers for nutrient recommendation and analysis."""
from __future__ import annotations

from typing import Dict

from .utils import load_dataset

DATA_FILE = "nutrient_guidelines.json"



# Cache dataset via ``load_dataset`` once at import time
_DATA: Dict[str, Dict[str, Dict[str, float]]] = load_dataset(DATA_FILE)


def list_supported_plants() -> list[str]:
    """Return all plant types with nutrient guidelines."""
    return sorted(_DATA.keys())


def get_recommended_levels(plant_type: str, stage: str) -> Dict[str, float]:
    """Return recommended nutrient levels for the given plant type and stage."""
    return _DATA.get(plant_type, {}).get(stage, {})


def calculate_deficiencies(
    current_levels: Dict[str, float],
    plant_type: str,
    stage: str,
) -> Dict[str, float]:
    """Return nutrient deficiencies compared to guidelines.

    Only nutrients below the recommended level are returned with the amount
    needed (ppm) to reach the target.
    """

    recommended = get_recommended_levels(plant_type, stage)
    deficiencies: Dict[str, float] = {}
    for nutrient, target in recommended.items():
        current = current_levels.get(nutrient, 0.0)
        diff = round(target - current, 2)
        if diff > 0:
            deficiencies[nutrient] = diff
    return deficiencies


def calculate_nutrient_balance(
    current_levels: Dict[str, float],
    plant_type: str,
    stage: str,
) -> Dict[str, float]:
    """Return ratio of current to recommended nutrient levels."""

    recommended = get_recommended_levels(plant_type, stage)
    ratios: Dict[str, float] = {}
    for nutrient, target in recommended.items():
        if target <= 0:
            continue
        current = current_levels.get(nutrient, 0.0)
        ratios[nutrient] = round(current / target, 2)
    return ratios

