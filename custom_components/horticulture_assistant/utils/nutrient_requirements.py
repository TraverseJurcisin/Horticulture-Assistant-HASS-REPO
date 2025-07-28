"""Load and evaluate baseline nutrient requirements for crops."""

from functools import lru_cache
from typing import Mapping, Dict

from plant_engine.plant_density import plants_per_area
from plant_engine.constants import get_stage_multiplier

from plant_engine.utils import load_dataset, normalize_key

DATA_FILE = "total_nutrient_requirements.json"


@lru_cache(maxsize=None)
def get_requirements(plant_type: str) -> Dict[str, float]:
    """Return daily nutrient requirements for ``plant_type``.

    Values are parsed from :data:`DATA_FILE` and converted to floats. Unknown
    plant types result in an empty dictionary.
    """
    data = load_dataset(DATA_FILE)
    plant = data.get(normalize_key(plant_type))
    if not isinstance(plant, Mapping):
        return {}
    req: Dict[str, float] = {}
    for nutrient, value in plant.items():
        try:
            req[nutrient] = float(value)
        except (TypeError, ValueError):
            continue
    return req


def calculate_deficit(current_totals: Mapping[str, float], plant_type: str) -> Dict[str, float]:
    """Return required nutrient amounts not yet supplied."""
    required = get_requirements(plant_type)
    deficit: Dict[str, float] = {}
    for nutrient, target in required.items():
        current = float(current_totals.get(nutrient, 0.0))
        diff = round(target - current, 2)
        if diff > 0:
            deficit[nutrient] = diff
    return deficit


def calculate_daily_area_requirements(
    plant_type: str, area_m2: float, stage: str | None = None
) -> Dict[str, float]:
    """Return daily nutrient grams required for ``area_m2`` of crop.

    Baseline per-plant requirements from :func:`get_requirements` are scaled
    using plant density guidelines and an optional stage multiplier.
    """

    if area_m2 <= 0:
        raise ValueError("area_m2 must be positive")

    per_plant = get_requirements(plant_type)
    if not per_plant:
        return {}

    count = plants_per_area(plant_type, area_m2)
    if count is None or count <= 0:
        return {}

    multiplier = get_stage_multiplier(stage) if stage else 1.0

    schedule: Dict[str, float] = {}
    for nutrient, grams in per_plant.items():
        total = grams * count * multiplier
        schedule[nutrient] = round(total, 2)

    return schedule


__all__ = [
    "get_requirements",
    "calculate_deficit",
    "calculate_daily_area_requirements",
]
