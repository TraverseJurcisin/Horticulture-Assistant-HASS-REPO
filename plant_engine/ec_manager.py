"""Electrical conductivity (EC) guidelines and helpers."""
from __future__ import annotations

from typing import Dict, Iterable

from .utils import load_dataset

DATA_FILE = "ec_guidelines.json"

_DATA: Dict[str, Dict[str, Iterable[float]]] = load_dataset(DATA_FILE)

__all__ = [
    "list_supported_plants",
    "get_ec_range",
    "recommend_ec_adjustment",
    "recommended_ec_setpoint",
]


def list_supported_plants() -> list[str]:
    """Return all plant types with EC guidelines."""
    return sorted(_DATA.keys())


def get_ec_range(plant_type: str, stage: str | None = None) -> list[float]:
    """Return EC range for ``plant_type`` and ``stage`` if available."""
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


def recommend_ec_adjustment(
    current_ec: float, plant_type: str, stage: str | None = None
) -> str | None:
    """Return 'increase' or 'decrease' recommendation for EC."""
    if current_ec <= 0:
        raise ValueError("current_ec must be positive")
    target = get_ec_range(plant_type, stage)
    if not target:
        return None
    low, high = target
    if current_ec < low:
        return "increase"
    if current_ec > high:
        return "decrease"
    return None


def recommended_ec_setpoint(
    plant_type: str, stage: str | None = None
) -> float | None:
    """Return midpoint EC setpoint for a plant stage if available."""
    rng = get_ec_range(plant_type, stage)
    if not rng:
        return None
    return round((rng[0] + rng[1]) / 2, 2)
