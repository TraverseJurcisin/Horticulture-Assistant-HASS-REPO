"""Load and evaluate baseline nutrient requirements for crops."""

from functools import lru_cache
from typing import Mapping, Dict

from plant_engine.utils import load_dataset, normalize_key

DATA_FILE = "total_nutrient_requirements.json"


@lru_cache(maxsize=None)
def list_supported_plants() -> tuple[str, ...]:
    """Return plant types with defined nutrient requirements."""
    data = load_dataset(DATA_FILE)
    return tuple(sorted(data.keys()))


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
    "list_supported_plants",
]
