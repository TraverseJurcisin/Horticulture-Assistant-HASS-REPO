"""EC (electrical conductivity) guidelines and helpers."""
from __future__ import annotations

from functools import lru_cache
from typing import Dict, Tuple

from .utils import load_dataset, normalize_key, list_dataset_entries

DATA_FILE = "ec_guidelines.json"

# cache dataset load
@lru_cache(maxsize=None)
def _data() -> Dict[str, Dict[str, Tuple[float, float]]]:
    return load_dataset(DATA_FILE)

__all__ = [
    "list_supported_plants",
    "get_ec_range",
    "get_optimal_ec",
    "classify_ec_level",
    "recommend_ec_adjustment",
]


def list_supported_plants() -> list[str]:
    """Return plant types with EC guidelines."""
    return list_dataset_entries(_data())


def get_ec_range(plant_type: str, stage: str | None = None) -> Tuple[float, float] | None:
    """Return (min, max) EC range for ``plant_type`` and ``stage`` if defined."""
    plant = _data().get(normalize_key(plant_type))
    if not plant:
        return None
    if stage:
        stage_key = normalize_key(stage)
        range_vals = plant.get(stage_key)
        if isinstance(range_vals, (list, tuple)) and len(range_vals) == 2:
            return float(range_vals[0]), float(range_vals[1])
    default = plant.get("default")
    if isinstance(default, (list, tuple)) and len(default) == 2:
        return float(default[0]), float(default[1])
    return None


def get_optimal_ec(plant_type: str, stage: str | None = None) -> float | None:
    """Return midpoint EC target for a plant stage if available."""

    rng = get_ec_range(plant_type, stage)
    if not rng:
        return None
    low, high = rng
    return round((low + high) / 2, 2)


def classify_ec_level(ec_ds_m: float, plant_type: str, stage: str | None = None) -> str:
    """Return ``'low'``, ``'optimal'`` or ``'high'`` based on guideline range."""
    rng = get_ec_range(plant_type, stage)
    if not rng:
        return "unknown"
    low, high = rng
    if ec_ds_m < low:
        return "low"
    if ec_ds_m > high:
        return "high"
    return "optimal"


def recommend_ec_adjustment(ec_ds_m: float, plant_type: str, stage: str | None = None) -> str:
    """Return adjustment suggestion for an EC reading."""
    level = classify_ec_level(ec_ds_m, plant_type, stage)
    if level == "low":
        return "increase"
    if level == "high":
        return "decrease"
    return "none"

