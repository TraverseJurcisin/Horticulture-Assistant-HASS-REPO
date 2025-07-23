"""Utility helpers for nutrient recommendation and analysis."""
from __future__ import annotations

from typing import Dict

from .utils import load_dataset, normalize_key

DATA_FILE = "nutrient_guidelines.json"


# Dataset cached via :func:`load_dataset` so this only happens once
_DATA: Dict[str, Dict[str, Dict[str, float]]] = load_dataset(DATA_FILE)

__all__ = [
    "list_supported_plants",
    "get_recommended_levels",
    "get_stage_guidelines",
    "get_all_recommended_levels",
    "calculate_deficiencies",
    "calculate_all_deficiencies",
    "calculate_nutrient_balance",
    "calculate_surplus",
    "calculate_all_surplus",
    "get_npk_ratio",
    "score_nutrient_levels",
]


def list_supported_plants() -> list[str]:
    """Return all plant types with nutrient guidelines."""
    return sorted(_DATA.keys())


def get_stage_guidelines(plant_type: str) -> Dict[str, Dict[str, float]]:
    """Return nutrient guidelines for all stages of ``plant_type``."""

    return _DATA.get(normalize_key(plant_type), {})


def get_recommended_levels(plant_type: str, stage: str) -> Dict[str, float]:
    """Return recommended nutrient levels for ``plant_type`` and ``stage``.

    Parameters are normalized using :func:`normalize_key` so lookups are
    case-insensitive and spaces are ignored. If no guidelines exist the
    function returns an empty dictionary.
    """

    plant = _DATA.get(normalize_key(plant_type))
    if not plant:
        return {}
    return plant.get(normalize_key(stage), {})


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


def score_nutrient_levels(
    current_levels: Dict[str, float], plant_type: str, stage: str
) -> float:
    """Return a 0-100 score for how close ``current_levels`` are to guidelines.

    Each nutrient is weighted equally. A perfect match yields ``100`` while
    values more than double or less than zero of the target contribute ``0`` to
    the overall score.
    """

    recommended = get_recommended_levels(plant_type, stage)
    if not recommended:
        return 0.0

    score = 0.0
    count = 0
    for nutrient, target in recommended.items():
        if target <= 0:
            continue
        current = current_levels.get(nutrient)
        if current is None:
            continue
        diff_ratio = abs(current - target) / target
        score += max(0.0, 1 - diff_ratio)
        count += 1

    if count == 0:
        return 0.0

    return round((score / count) * 100, 1)


def get_all_recommended_levels(plant_type: str, stage: str) -> Dict[str, float]:
    """Return combined macro and micro nutrient guidelines."""

    levels = get_recommended_levels(plant_type, stage)
    from .micro_manager import get_recommended_levels as _micro

    levels.update(_micro(plant_type, stage))
    return levels


def calculate_all_deficiencies(
    current_levels: Dict[str, float], plant_type: str, stage: str
) -> Dict[str, float]:
    """Return overall nutrient deficiencies including micronutrients."""

    deficits = calculate_deficiencies(current_levels, plant_type, stage)
    from .micro_manager import calculate_deficiencies as _micro_def

    deficits.update(_micro_def(current_levels, plant_type, stage))
    return deficits


def calculate_all_surplus(
    current_levels: Dict[str, float], plant_type: str, stage: str
) -> Dict[str, float]:
    """Return overall nutrient surplus including micronutrients."""

    surplus = calculate_surplus(current_levels, plant_type, stage)
    from .micro_manager import calculate_surplus as _micro_surplus

    surplus.update(_micro_surplus(current_levels, plant_type, stage))
    return surplus


