"""Load and evaluate baseline nutrient requirements for crops."""

from functools import lru_cache
from typing import Mapping, Dict

from plant_engine.utils import load_dataset, normalize_key

DATA_FILE = "total_nutrient_requirements.json"
STAGE_DATA_FILE = "stage_nutrient_requirements.json"


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


__all__ = [
    "get_requirements",
    "calculate_deficit",
    "get_stage_requirements",
    "calculate_stage_deficit",
]


@lru_cache(maxsize=None)
def get_stage_requirements(plant_type: str, stage: str) -> Dict[str, float]:
    """Return daily nutrient requirements for a specific growth stage."""

    data = load_dataset(STAGE_DATA_FILE)
    plant = data.get(normalize_key(plant_type))
    if not isinstance(plant, Mapping):
        return {}
    stage_data = plant.get(normalize_key(stage))
    if not isinstance(stage_data, Mapping):
        return {}
    req: Dict[str, float] = {}
    for nutrient, value in stage_data.items():
        try:
            req[nutrient] = float(value)
        except (TypeError, ValueError):
            continue
    return req


def calculate_stage_deficit(
    current_totals: Mapping[str, float], plant_type: str, stage: str
) -> Dict[str, float]:
    """Return required nutrient amounts for the given stage not yet supplied."""

    required = get_stage_requirements(plant_type, stage)
    deficit: Dict[str, float] = {}
    for nutrient, target in required.items():
        current = float(current_totals.get(nutrient, 0.0))
        diff = round(target - current, 2)
        if diff > 0:
            deficit[nutrient] = diff
    return deficit
