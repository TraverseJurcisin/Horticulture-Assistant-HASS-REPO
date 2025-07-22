"""Micronutrient guideline utilities."""
from __future__ import annotations

from typing import Dict, Mapping

from .utils import load_dataset

DATA_FILE = "micronutrient_guidelines.json"

# Cached dataset loaded once
_DATA: Dict[str, Dict[str, Dict[str, float]]] = load_dataset(DATA_FILE)

__all__ = [
    "list_supported_plants",
    "get_recommended_levels",
    "calculate_deficiencies",
]


def _norm(key: str) -> str:
    """Normalize a key for case-insensitive lookup."""
    return key.lower()


def list_supported_plants() -> list[str]:
    """Return plants with micronutrient guidelines."""
    return sorted(_DATA.keys())


def get_recommended_levels(plant_type: str, stage: str) -> Dict[str, float]:
    """Return recommended micronutrient levels."""
    plant = _DATA.get(_norm(plant_type))
    if not plant:
        return {}
    return plant.get(_norm(stage), {})


def calculate_deficiencies(
    current_levels: Mapping[str, float],
    plant_type: str,
    stage: str,
) -> Dict[str, float]:
    """Return micronutrient deficiencies compared to guidelines."""
    target = get_recommended_levels(plant_type, stage)
    deficits: Dict[str, float] = {}
    for nutrient, rec in target.items():
        diff = round(rec - current_levels.get(nutrient, 0.0), 2)
        if diff > 0:
            deficits[nutrient] = diff
    return deficits
