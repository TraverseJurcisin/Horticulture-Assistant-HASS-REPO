"""Utility helpers for crop nutrient requirements.

The dataset :data:`DATA_FILE` contains average daily NPK needs for each
registered plant.  This module exposes simple helpers to retrieve those values,
compare them against accumulated nutrient totals and estimate totals for a
time span.
"""

from functools import lru_cache
from typing import Dict, Mapping

from plant_engine.utils import load_dataset, normalize_key

DATA_FILE = "total_nutrient_requirements.json"


@lru_cache(maxsize=None)
def get_requirements(plant_type: str) -> Dict[str, float]:
    """Return daily nutrient requirements for ``plant_type``.

    Unknown plants yield an empty mapping. Values are coerced to ``float`` and
    invalid entries are skipped gracefully.
    """

    data = load_dataset(DATA_FILE)
    raw = data.get(normalize_key(plant_type))
    if not isinstance(raw, Mapping):
        return {}

    return {
        nutrient: float(value)
        for nutrient, value in raw.items()
        if isinstance(value, (int, float, str))
    }


def calculate_deficit(current_totals: Mapping[str, float], plant_type: str) -> Dict[str, float]:
    """Return required nutrient amounts not yet supplied."""

    required = get_requirements(plant_type)
    return {
        nutrient: round(target - float(current_totals.get(nutrient, 0.0)), 2)
        for nutrient, target in required.items()
        if target > float(current_totals.get(nutrient, 0.0))
    }


def calculate_surplus(current_totals: Mapping[str, float], plant_type: str) -> Dict[str, float]:
    """Return nutrient amounts exceeding the recommended totals."""

    required = get_requirements(plant_type)
    surplus: Dict[str, float] = {}
    for nutrient, target in required.items():
        try:
            current = float(current_totals.get(nutrient, 0.0))
        except (TypeError, ValueError):
            current = 0.0
        if current > target:
            surplus[nutrient] = round(current - target, 2)
    return surplus


def calculate_cumulative_requirements(plant_type: str, days: int) -> Dict[str, float]:
    """Return total nutrient needs over ``days``.

    Values are derived from :func:`get_requirements` and multiplied by the
    provided day count. Unknown plants or non-positive ``days`` yield an empty
    mapping.
    """

    if days <= 0:
        return {}

    daily = get_requirements(plant_type)
    return {nutrient: round(value * days, 2) for nutrient, value in daily.items()}


__all__ = [
    "get_requirements",
    "calculate_deficit",
    "calculate_surplus",
    "calculate_cumulative_requirements",
]
