"""EC (electrical conductivity) guidelines and helpers."""
from __future__ import annotations

from functools import lru_cache
from typing import Dict, Tuple, Mapping

from .constants import get_stage_multiplier

from .utils import load_dataset, normalize_key, list_dataset_entries

DATA_FILE = "ec/ec_guidelines.json"
RECIPE_FILE = "stock/stock_solution_recipes.json"
ADJUST_FILE = "ec/ec_adjustment_factors.json"

# cache dataset load
@lru_cache(maxsize=None)
def _data() -> Dict[str, Dict[str, Tuple[float, float]]]:
    return load_dataset(DATA_FILE)


@lru_cache(maxsize=None)
def _recipes() -> Dict[str, Dict[str, Mapping[str, float]]]:
    return load_dataset(RECIPE_FILE)


@lru_cache(maxsize=None)
def _adjust() -> Dict[str, float]:
    return load_dataset(ADJUST_FILE)

__all__ = [
    "list_supported_plants",
    "get_ec_range",
    "get_optimal_ec",
    "get_stage_adjusted_ec_range",
    "classify_ec_level",
    "recommend_ec_adjustment",
    "estimate_ec_adjustment_volume",
    "recommend_ec_correction",
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


def get_stage_adjusted_ec_range(
    plant_type: str, stage: str | None = None
) -> Tuple[float, float] | None:
    """Return EC range scaled by the stage multiplier if available."""

    rng = get_ec_range(plant_type, stage)
    if not rng:
        return None
    low, high = rng
    mult = get_stage_multiplier(stage or "")
    return round(low * mult, 2), round(high * mult, 2)


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


def estimate_ec_adjustment_volume(
    current_ec_ds_m: float,
    target_ec_ds_m: float,
    volume_l: float,
    stock: str,
) -> float | None:
    """Return ml of ``stock`` to raise EC from current to target."""
    if volume_l <= 0:
        raise ValueError("volume_l must be positive")
    factor = _adjust().get(stock)
    if not factor:
        return None
    delta = target_ec_ds_m - current_ec_ds_m
    if delta <= 0:
        return 0.0
    ml = delta * volume_l / factor
    return round(ml, 2)


def recommend_ec_correction(
    current_ec_ds_m: float,
    plant_type: str,
    stage: str,
    volume_l: float,
) -> Dict[str, float] | None:
    """Return stock solution volumes or dilution needed for EC correction."""

    target = get_optimal_ec(plant_type, stage)
    if target is None:
        return None
    delta = round(target - current_ec_ds_m, 2)
    if abs(delta) < 0.01:
        return {}
    if delta < 0:
        new_volume = volume_l * (current_ec_ds_m / target)
        return {"dilute_l": round(new_volume - volume_l, 2)}

    recipe = _recipes().get(normalize_key(plant_type), {}).get(normalize_key(stage), {})
    if not isinstance(recipe, Mapping) or not recipe:
        recipe = {"stock_a": 1.0}
    total_ratio = sum(float(v) for v in recipe.values() if isinstance(v, (int, float)))
    factors = _adjust()
    result: Dict[str, float] = {}
    for stock, ratio in recipe.items():
        factor = factors.get(stock)
        if factor and total_ratio > 0:
            ml = (delta * volume_l / factor) * (float(ratio) / total_ratio)
            result[stock] = round(ml, 2)
    return result or None

