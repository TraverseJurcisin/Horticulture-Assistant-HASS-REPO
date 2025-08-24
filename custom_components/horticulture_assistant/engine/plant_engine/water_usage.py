"""Lookup daily water use estimates for irrigation planning."""

from __future__ import annotations

from .utils import list_dataset_entries, load_dataset, normalize_key

DATA_FILE = "water/water_usage_guidelines.json"

_DATA: dict[str, dict[str, float]] = load_dataset(DATA_FILE)

from .growth_stage import get_stage_duration, list_growth_stages
from .plant_density import get_spacing_cm

__all__ = [
    "list_supported_plants",
    "get_daily_use",
    "estimate_area_use",
    "estimate_area_water_cost",
    "estimate_daily_plant_cost",
    "estimate_daily_use_from_et0",
    "estimate_stage_total_use",
    "estimate_cycle_total_use",
    "estimate_stage_water_cost",
    "estimate_cycle_water_cost",
]


def list_supported_plants() -> list[str]:
    """Return all plant types with water use data."""
    return list_dataset_entries(_DATA)


def get_daily_use(plant_type: str, stage: str) -> float:
    """Return daily water usage in milliliters for a plant stage."""
    plant = _DATA.get(normalize_key(plant_type))
    if not plant:
        return 0.0
    try:
        return float(plant.get(normalize_key(stage), 0.0))
    except (TypeError, ValueError):
        return 0.0


def estimate_daily_use_from_et0(
    plant_type: str,
    stage: str,
    et0_mm_day: float,
    zone: str | None = None,
) -> float:
    """Return estimated daily water use per plant from ET₀ and crop coefficients.

    Parameters
    ----------
    plant_type : str
        Plant identifier for crop coefficient and spacing lookup.
    stage : str
        Current growth stage for crop coefficient lookup.
    et0_mm_day : float
        Reference evapotranspiration in millimeters per day.
    zone : str, optional
        Climate zone for ET₀ adjustment using :mod:`plant_engine.et_model`.

    Returns
    -------
    float
        Estimated milliliters of water needed per plant each day. ``0.0`` is
        returned if required dataset information is missing.
    """

    if et0_mm_day <= 0:
        return 0.0

    if zone:
        from .et_model import adjust_et0_for_climate

        et0_mm_day = adjust_et0_for_climate(et0_mm_day, zone)

    from .et_model import calculate_eta

    kc_data = load_dataset("coefficients/crop_coefficients.json")
    plant = kc_data.get(normalize_key(plant_type), {})
    kc = plant.get(normalize_key(stage)) or plant.get("default")
    try:
        kc_val = float(kc) if kc is not None else 1.0
    except (TypeError, ValueError):
        kc_val = 1.0

    spacing = get_spacing_cm(plant_type)
    if spacing is None or spacing <= 0:
        return 0.0

    area_m2 = (spacing / 100) ** 2
    eta = calculate_eta(et0_mm_day, kc_val)
    return round(eta * area_m2 * 1000.0, 1)


def estimate_area_use(plant_type: str, stage: str, area_m2: float) -> float:
    """Return daily water requirement for ``area_m2`` of crop.

    The calculation multiplies per-plant usage by the estimated plant count
    based on recommended spacing from :mod:`plant_engine.plant_density`.
    ``area_m2`` must be positive or a ``ValueError`` is raised.
    """

    if area_m2 <= 0:
        raise ValueError("area_m2 must be positive")

    spacing_cm = get_spacing_cm(plant_type)
    if spacing_cm is None or spacing_cm <= 0:
        return 0.0

    plants = area_m2 / ((spacing_cm / 100) ** 2)
    per_plant = get_daily_use(plant_type, stage)
    return round(plants * per_plant, 1)


def estimate_stage_total_use(plant_type: str, stage: str) -> float:
    """Return total water use for a stage based on duration days."""

    daily = get_daily_use(plant_type, stage)
    duration = get_stage_duration(plant_type, stage)
    if daily <= 0 or duration is None:
        return 0.0
    return round(daily * duration, 1)


def estimate_cycle_total_use(plant_type: str) -> float:
    """Return total water requirement for the entire crop cycle."""

    total = 0.0
    for stage in list_growth_stages(plant_type):
        daily = get_daily_use(plant_type, stage)
        duration = get_stage_duration(plant_type, stage)
        if daily > 0 and duration:
            total += daily * duration
    return round(total, 1)


def estimate_area_water_cost(
    plant_type: str,
    stage: str,
    area_m2: float,
    region: str | None = None,
) -> float:
    """Return daily watering cost for ``area_m2`` of crop."""

    volume_ml = estimate_area_use(plant_type, stage, area_m2)
    if volume_ml <= 0:
        return 0.0
    from .water_costs import estimate_water_cost

    return estimate_water_cost(volume_ml / 1000.0, region)


def estimate_daily_plant_cost(
    plant_type: str,
    stage: str,
    num_plants: int,
    region: str | None = None,
) -> float:
    """Return daily irrigation cost for ``num_plants`` of a plant stage."""

    if num_plants <= 0:
        raise ValueError("num_plants must be positive")

    per_plant = get_daily_use(plant_type, stage)
    if per_plant <= 0:
        return 0.0
    volume_l = per_plant * num_plants / 1000.0
    from .water_costs import estimate_water_cost

    return estimate_water_cost(volume_l, region)


def estimate_stage_water_cost(plant_type: str, stage: str, region: str | None = None) -> float:
    """Return estimated cost for watering ``plant_type`` during ``stage``."""

    total_ml = estimate_stage_total_use(plant_type, stage)
    if total_ml <= 0:
        return 0.0
    from .water_costs import estimate_water_cost

    return estimate_water_cost(total_ml / 1000.0, region)


def estimate_cycle_water_cost(plant_type: str, region: str | None = None) -> float:
    """Return estimated water cost for the entire crop cycle."""

    total_ml = estimate_cycle_total_use(plant_type)
    if total_ml <= 0:
        return 0.0
    from .water_costs import estimate_water_cost

    return estimate_water_cost(total_ml / 1000.0, region)
