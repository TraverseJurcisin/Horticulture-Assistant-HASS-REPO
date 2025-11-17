"""Utility helpers for crop nutrient requirements.

The dataset :data:`DATA_FILE` contains average daily NPK needs for each
registered plant.  This module exposes simple helpers to retrieve those values,
compare them against accumulated nutrient totals and estimate totals for a
time span.
"""

from collections.abc import Mapping
from functools import cache

try:  # pragma: no cover - prefer system plant_engine
    from plant_engine.root_temperature import get_uptake_factor
    from plant_engine.utils import load_dataset, normalize_key
except ModuleNotFoundError:  # pragma: no cover - fallback to bundled copy
    from ..engine.plant_engine.root_temperature import get_uptake_factor
    from ..engine.plant_engine.utils import load_dataset, normalize_key

DATA_FILE = "nutrients/total_nutrient_requirements.json"


@cache
def get_requirements(plant_type: str) -> dict[str, float]:
    """Return daily nutrient requirements for ``plant_type``.

    Unknown plants yield an empty mapping. Values are coerced to ``float`` and
    invalid entries are skipped gracefully.
    """

    data = load_dataset(DATA_FILE)
    raw = data.get(normalize_key(plant_type))
    if not isinstance(raw, Mapping):
        return {}

    parsed: dict[str, float] = {}
    for nutrient, value in raw.items():
        if not isinstance(value, (int, float, str)):
            continue

        try:
            parsed[nutrient] = float(value)
        except (TypeError, ValueError):
            continue

    return parsed


def calculate_deficit(current_totals: Mapping[str, float], plant_type: str) -> dict[str, float]:
    """Return required nutrient amounts not yet supplied."""

    required = get_requirements(plant_type)
    return {
        nutrient: round(target - float(current_totals.get(nutrient, 0.0)), 2)
        for nutrient, target in required.items()
        if target > float(current_totals.get(nutrient, 0.0))
    }


def calculate_cumulative_requirements(plant_type: str, days: int) -> dict[str, float]:
    """Return total nutrient needs over ``days``.

    Values are derived from :func:`get_requirements` and multiplied by the
    provided day count. Unknown plants or non-positive ``days`` yield an empty
    mapping.
    """

    if days <= 0:
        return {}

    daily = get_requirements(plant_type)
    return {nutrient: round(value * days, 2) for nutrient, value in daily.items()}


def get_temperature_adjusted_requirements(plant_type: str, root_temp_c: float) -> dict[str, float]:
    """Return daily requirements adjusted for root zone temperature."""

    base = get_requirements(plant_type)
    if not base:
        return {}

    factor = get_uptake_factor(root_temp_c, plant_type)
    if factor <= 0:
        return dict.fromkeys(base, 0.0)

    return {nutrient: round(value / factor, 2) for nutrient, value in base.items()}


def calculate_temperature_adjusted_cumulative_requirements(
    plant_type: str, days: int, root_temp_c: float
) -> dict[str, float]:
    """Return total nutrient needs adjusted for root zone temperature."""

    if days <= 0:
        return {}

    daily = get_temperature_adjusted_requirements(plant_type, root_temp_c)
    return {nutrient: round(value * days, 2) for nutrient, value in daily.items()}


__all__ = [
    "get_requirements",
    "calculate_deficit",
    "calculate_cumulative_requirements",
    "get_temperature_adjusted_requirements",
    "calculate_temperature_adjusted_cumulative_requirements",
]
