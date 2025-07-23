"""pH management utilities."""
from __future__ import annotations

from typing import Dict, Iterable

from .utils import load_dataset

DATA_FILE = "ph_guidelines.json"
ADJUST_FILE = "ph_adjustment_factors.json"
MEDIUM_FILE = "growth_medium_ph_ranges.json"

# Cached dataset loaded once
_DATA: Dict[str, Dict[str, Iterable[float]]] = load_dataset(DATA_FILE)
_ADJUST: Dict[str, Dict[str, float]] = load_dataset(ADJUST_FILE)
_MEDIUM: Dict[str, Iterable[float]] = load_dataset(MEDIUM_FILE)

__all__ = [
    "list_supported_plants",
    "get_ph_range",
    "recommend_ph_adjustment",
    "recommended_ph_setpoint",
    "estimate_ph_adjustment_volume",
    "get_medium_ph_range",
    "recommend_medium_ph_adjustment",
    "recommended_ph_for_medium",
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


def estimate_ph_adjustment_volume(
    current_ph: float,
    target_ph: float,
    volume_l: float,
    product: str,
) -> float | None:
    """Return milliliters of ``product`` to adjust solution pH.

    The :data:`ph_adjustment_factors.json` dataset defines the expected pH
    change per milliliter added to one liter of solution. The required volume
    scales linearly with the total solution volume. ``None`` is returned if the
    product is unknown.
    """

    if volume_l <= 0:
        raise ValueError("volume_l must be positive")

    delta = target_ph - current_ph
    if delta == 0:
        return 0.0

    info = _ADJUST.get(product)
    if not info:
        return None
    effect = info.get("effect_per_ml_per_l")
    if not isinstance(effect, (int, float)) or effect == 0:
        return None

    # Effect per ml for the whole volume
    effect_total = effect / volume_l
    ml_needed = delta / effect_total
    return round(abs(ml_needed), 2)


def get_medium_ph_range(medium: str) -> list[float]:
    """Return optimal pH range for a growing medium."""

    rng = _MEDIUM.get(medium.lower())
    if isinstance(rng, Iterable):
        vals = list(rng)
        if len(vals) == 2:
            return [float(vals[0]), float(vals[1])]
    return []


def recommend_medium_ph_adjustment(current_ph: float, medium: str) -> str | None:
    """Return pH adjustment guidance based on growing medium."""

    target = get_medium_ph_range(medium)
    if not target:
        return None
    low, high = target
    if current_ph < low:
        return "increase"
    if current_ph > high:
        return "decrease"
    return None


def recommended_ph_for_medium(medium: str) -> float | None:
    """Return midpoint pH setpoint for the medium if available."""

    rng = get_medium_ph_range(medium)
    if not rng:
        return None
    return round((rng[0] + rng[1]) / 2, 2)
