"""Nutrient mobilization factors for deficiency correction."""
from __future__ import annotations

from functools import lru_cache
from typing import Mapping, Dict

from .utils import load_dataset, normalize_key

DATA_FILE = "nutrient_mobilization.json"

@lru_cache(maxsize=None)
def _data() -> Dict[str, Dict[str, float]]:
    raw = load_dataset(DATA_FILE)
    data: Dict[str, Dict[str, float]] = {}
    for plant, vals in raw.items():
        if not isinstance(vals, Mapping):
            continue
        key = normalize_key(plant)
        data[key] = {n: float(v) for n, v in vals.items() if isinstance(v, (int, float))}
    return data


def get_mobilization_factor(nutrient: str, plant_type: str | None = None) -> float:
    """Return mobilization factor for ``nutrient`` and optional ``plant_type``."""
    if plant_type:
        plant = _data().get(normalize_key(plant_type), {})
        if nutrient in plant:
            return float(plant[nutrient])
    return float(_data().get("default", {}).get(nutrient, 1.0))


def apply_mobilization(schedule: Mapping[str, float], plant_type: str | None = None) -> Dict[str, float]:
    """Return ``schedule`` scaled by mobilization factors."""
    adjusted: Dict[str, float] = {}
    for nutrient, grams in schedule.items():
        factor = get_mobilization_factor(nutrient, plant_type)
        try:
            g = float(grams)
        except (TypeError, ValueError):
            continue
        adjusted[nutrient] = round(g / factor, 2) if factor and factor > 0 else g
    return adjusted

__all__ = ["get_mobilization_factor", "apply_mobilization"]
