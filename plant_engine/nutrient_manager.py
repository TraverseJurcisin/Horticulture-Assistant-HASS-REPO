"""Utility helpers for nutrient recommendation and analysis."""
from __future__ import annotations

from typing import Dict

from .utils import load_dataset

DATA_FILE = "nutrient_guidelines.json"


# Dataset cached via :func:`load_dataset` so this only happens once
_DATA: Dict[str, Dict[str, Dict[str, float]]] = load_dataset(DATA_FILE)

__all__ = [
    "list_supported_plants",
    "get_recommended_levels",
    "calculate_deficiencies",
    "calculate_nutrient_balance",
    "calculate_surplus",
    "get_npk_ratio",
]


def list_supported_plants() -> list[str]:
    """Return all plant types with nutrient guidelines."""
    return sorted(_DATA.keys())


def get_recommended_levels(plant_type: str, stage: str) -> Dict[str, float]:
    """Return recommended nutrient levels for ``plant_type`` and ``stage``.

    Parameters are matched case-insensitively. An empty dictionary is returned
    if no guidelines exist for the provided keys.
    """
    plant = _DATA.get(plant_type.lower())
    if not plant:
        return {}
    return plant.get(stage.lower(), {})


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


def calculate_surplus(
    current_levels: Dict[str, float],
    plant_type: str,
    stage: str,
) -> Dict[str, float]:
    """Return nutrient amounts exceeding recommendations."""

    recommended = get_recommended_levels(plant_type, stage)
    surplus: Dict[str, float] = {}
    for nutrient, target in recommended.items():
        current = current_levels.get(nutrient, 0.0)
        diff = round(current - target, 2)
        if diff > 0:
            surplus[nutrient] = diff
    return surplus


def get_npk_ratio(plant_type: str, stage: str) -> Dict[str, float]:
    """Return normalized N:P:K ratio for a plant stage.

    The ratios sum to 1.0. If any nutrient is missing or all values are zero,
    ``{"N": 0.0, "P": 0.0, "K": 0.0}`` is returned.
    """

    rec = get_recommended_levels(plant_type, stage)
    n = rec.get("N", 0.0)
    p = rec.get("P", 0.0)
    k = rec.get("K", 0.0)
    total = n + p + k
    if total <= 0:
        return {"N": 0.0, "P": 0.0, "K": 0.0}

    return {
        "N": round(n / total, 2),
        "P": round(p / total, 2),
        "K": round(k / total, 2),
    }


