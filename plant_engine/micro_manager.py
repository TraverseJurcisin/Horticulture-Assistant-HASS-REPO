"""Micronutrient guideline utilities."""
from __future__ import annotations

from typing import Dict, Mapping

from .utils import load_dataset, normalize_key, list_dataset_entries

DATA_FILE = "micronutrient_guidelines.json"

# Cached dataset loaded once
_DATA: Dict[str, Dict[str, Dict[str, float]]] = load_dataset(DATA_FILE)

__all__ = [
    "list_supported_plants",
    "get_recommended_levels",
    "calculate_deficiencies",
    "calculate_surplus",
    "calculate_balance",
]


def list_supported_plants() -> list[str]:
    """Return plants with micronutrient guidelines."""
    return list_dataset_entries(_DATA)


def get_recommended_levels(plant_type: str, stage: str) -> Dict[str, float]:
    """Return recommended micronutrient levels."""
    plant = _DATA.get(normalize_key(plant_type))
    if not plant:
        return {}
    return plant.get(normalize_key(stage), {})


def _calculate_diff(
    current_levels: Mapping[str, float],
    plant_type: str,
    stage: str,
    *,
    mode: str,
) -> Dict[str, float]:
    """Return difference from guidelines for ``mode``.

    ``mode`` may be ``"deficit"`` or ``"surplus"``.
    Positive values are returned for nutrients requiring adjustment.
    """

    target = get_recommended_levels(plant_type, stage)
    result: Dict[str, float] = {}
    for nutrient, rec in target.items():
        try:
            current = float(current_levels.get(nutrient, 0.0))
        except (TypeError, ValueError):
            current = 0.0
        delta = round(rec - current, 2)
        if mode == "deficit" and delta > 0:
            result[nutrient] = delta
        elif mode == "surplus" and delta < 0:
            result[nutrient] = -delta
    return result


def calculate_deficiencies(
    current_levels: Mapping[str, float],
    plant_type: str,
    stage: str,
) -> Dict[str, float]:
    """Return micronutrient deficiencies compared to guidelines."""
    return _calculate_diff(current_levels, plant_type, stage, mode="deficit")


def calculate_surplus(
    current_levels: Mapping[str, float],
    plant_type: str,
    stage: str,
) -> Dict[str, float]:
    """Return micronutrient surpluses above recommended levels."""

    return _calculate_diff(current_levels, plant_type, stage, mode="surplus")


def calculate_balance(
    current_levels: Mapping[str, float],
    plant_type: str,
    stage: str,
) -> Dict[str, float]:
    """Return ratio of current to recommended micronutrient levels."""

    target = get_recommended_levels(plant_type, stage)
    ratios: Dict[str, float] = {}
    for nutrient, rec in target.items():
        if rec <= 0:
            continue
        try:
            current = float(current_levels.get(nutrient, 0.0))
        except (TypeError, ValueError):
            current = 0.0
        ratios[nutrient] = round(current / rec, 2)
    return ratios
