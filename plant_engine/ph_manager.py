"""pH management utilities."""
from __future__ import annotations

from typing import Dict, Iterable, Mapping

from .utils import load_dataset

DATA_FILE = "ph_guidelines.json"
PH_AVAIL_FILE = "ph_nutrient_availability.json"

# Cached dataset loaded once
_DATA: Dict[str, Dict[str, Iterable[float]]] = load_dataset(DATA_FILE)
# Map of pH value to relative nutrient availability (0-1)
_PH_AVAIL: Dict[str, Dict[str, float]] = load_dataset(PH_AVAIL_FILE)

__all__ = [
    "list_supported_plants",
    "get_ph_range",
    "recommend_ph_adjustment",
    "recommended_ph_setpoint",
    "get_nutrient_availability",
    "limiting_nutrients",
]


def list_supported_plants() -> list[str]:
    """Return all plant types with pH guidelines."""
    return sorted(_DATA.keys())


def get_ph_range(plant_type: str, stage: str | None = None) -> list[float]:
    """Return pH range for ``plant_type`` and ``stage``."""
    data = _DATA.get(plant_type.lower())
    if not data:
        return []
    if stage and stage in data:
        rng = data[stage]
    else:
        rng = data.get("optimal")
    if isinstance(rng, Iterable):
        values = list(rng)
        if len(values) == 2:
            return [float(values[0]), float(values[1])]
    return []


def recommend_ph_adjustment(
    current_ph: float, plant_type: str, stage: str | None = None
) -> str | None:
    """Return 'increase' or 'decrease' recommendation for pH."""
    if current_ph <= 0:
        raise ValueError("current_ph must be positive")
    target = get_ph_range(plant_type, stage)
    if not target:
        return None
    low, high = target
    if current_ph < low:
        return "increase"
    if current_ph > high:
        return "decrease"
    return None


def recommended_ph_setpoint(plant_type: str, stage: str | None = None) -> float | None:
    """Return midpoint pH setpoint for a plant stage if available."""

    rng = get_ph_range(plant_type, stage)
    if not rng:
        return None
    return round((rng[0] + rng[1]) / 2, 2)


def get_nutrient_availability(ph: float) -> Dict[str, float]:
    """Return relative nutrient availability for a given pH.

    Values are normalized between 0 and 1. pH values outside the dataset
    range are clamped to the nearest available entry.
    """
    if ph <= 0:
        raise ValueError("ph must be positive")
    if not _PH_AVAIL:
        return {}
    keys = sorted(float(k) for k in _PH_AVAIL)
    nearest = min(keys, key=lambda x: abs(x - ph))
    data = _PH_AVAIL.get(str(nearest), {})
    return {k: float(v) for k, v in data.items()}


def limiting_nutrients(ph: float, threshold: float = 0.7) -> list[str]:
    """Return nutrients with availability below ``threshold`` at ``ph``."""
    availability = get_nutrient_availability(ph)
    return sorted(n for n, val in availability.items() if val < threshold)
