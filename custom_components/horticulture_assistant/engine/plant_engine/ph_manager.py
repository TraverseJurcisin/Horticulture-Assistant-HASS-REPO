"""pH management utilities."""

from __future__ import annotations

from typing import Dict, Iterable

from .utils import list_dataset_entries, load_dataset, stage_value, normalize_key

DATA_FILE = "ph/ph_guidelines.json"
ADJUST_FILE = "ph/ph_adjustment_factors.json"
MEDIUM_FILE = "ph/growth_medium_ph_ranges.json"
SOIL_PH_FILE = "soil/soil_ph_guidelines.json"

# Cached dataset loaded once
_DATA: Dict[str, Dict[str, Iterable[float]]] = load_dataset(DATA_FILE)
_ADJUST: Dict[str, Dict[str, float]] = load_dataset(ADJUST_FILE)
_MEDIUM: Dict[str, Iterable[float]] = load_dataset(MEDIUM_FILE)
_SOIL: Dict[str, Iterable[float]] = load_dataset(SOIL_PH_FILE)

__all__ = [
    "list_supported_plants",
    "get_ph_range",
    "recommend_ph_adjustment",
    "classify_ph",
    "recommended_ph_setpoint",
    "estimate_ph_adjustment_volume",
    "recommend_solution_ph_adjustment",
    "recommend_ph_correction",
    "get_medium_ph_range",
    "recommend_medium_ph_adjustment",
    "recommended_ph_for_medium",
    "get_soil_ph_range",
    "recommend_soil_ph_adjustment",
    "classify_soil_ph",
]


def list_supported_plants() -> list[str]:
    """Return all plant types with pH guidelines."""
    return list_dataset_entries(_DATA)


def get_ph_range(plant_type: str, stage: str | None = None) -> list[float]:
    """Return pH range for ``plant_type`` and ``stage``."""

    rng = stage_value(_DATA, plant_type, stage)
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


def classify_ph(current_ph: float, plant_type: str, stage: str | None = None) -> str | None:
    """Return 'low', 'optimal' or 'high' for ``current_ph``.

    The classification is based on :func:`get_ph_range`. ``None`` is returned
    when no guideline exists for the specified plant or stage.
    """

    if current_ph <= 0:
        raise ValueError("current_ph must be positive")

    target = get_ph_range(plant_type, stage)
    if not target:
        return None

    low, high = target
    if current_ph < low:
        return "low"
    if current_ph > high:
        return "high"
    return "optimal"


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


def recommend_solution_ph_adjustment(
    current_ph: float,
    plant_type: str,
    stage: str | None,
    volume_l: float,
    product: str,
) -> float | None:
    """Return adjustment volume to reach the recommended pH setpoint.

    This helper combines :func:`recommended_ph_setpoint` and
    :func:`estimate_ph_adjustment_volume` for convenience when calculating
    nutrient solution corrections.
    """

    target = recommended_ph_setpoint(plant_type, stage)
    if target is None:
        return None
    return estimate_ph_adjustment_volume(current_ph, target, volume_l, product)


def recommend_ph_correction(
    current_ph: float,
    plant_type: str,
    stage: str | None,
    volume_l: float,
    *,
    up_product: str = "ph_up",
    down_product: str = "ph_down",
) -> tuple[str, float] | None:
    """Return fertilizer product and volume to correct solution pH.

    This helper selects ``up_product`` when the current pH is below the
    recommended range and ``down_product`` when it is above. ``None`` is
    returned if the pH is already within range or the adjustment volume cannot
    be calculated.
    """

    target = recommended_ph_setpoint(plant_type, stage)
    if target is None:
        return None

    delta = target - current_ph
    if abs(delta) < 0.01:
        return None

    product = up_product if delta > 0 else down_product
    volume = estimate_ph_adjustment_volume(current_ph, target, volume_l, product)
    if volume is None:
        return None
    return product, volume


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


def get_soil_ph_range(plant_type: str) -> list[float]:
    """Return optimal soil pH range for ``plant_type``."""

    rng = _SOIL.get(normalize_key(plant_type))
    if isinstance(rng, Iterable):
        vals = list(rng)
        if len(vals) == 2:
            return [float(vals[0]), float(vals[1])]
    return []


def recommend_soil_ph_adjustment(current_ph: float, plant_type: str) -> str | None:
    """Return soil pH adjustment recommendation for ``plant_type``."""

    if current_ph <= 0:
        raise ValueError("current_ph must be positive")
    rng = get_soil_ph_range(plant_type)
    if not rng:
        return None
    low, high = rng
    if current_ph < low:
        return "increase"
    if current_ph > high:
        return "decrease"
    return None


def classify_soil_ph(current_ph: float, plant_type: str) -> str | None:
    """Return 'low', 'optimal' or 'high' classification for soil pH."""

    if current_ph <= 0:
        raise ValueError("current_ph must be positive")
    rng = get_soil_ph_range(plant_type)
    if not rng:
        return None
    low, high = rng
    if current_ph < low:
        return "low"
    if current_ph > high:
        return "high"
    return "optimal"
