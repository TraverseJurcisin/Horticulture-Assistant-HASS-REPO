"""Lookup daily water use estimates for irrigation planning."""
from __future__ import annotations

from typing import Dict

from .utils import load_dataset, normalize_key, list_dataset_entries

DATA_FILE = "water_usage_guidelines.json"

_DATA: Dict[str, Dict[str, float]] = load_dataset(DATA_FILE)

from .plant_density import get_spacing_cm
from .growth_stage import get_stage_duration, list_growth_stages

__all__ = [
    "list_supported_plants",
    "get_daily_use",
    "estimate_area_use",
    "estimate_area_water_cost",
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


def estimate_stage_water_cost(
    plant_type: str, stage: str, region: str | None = None
) -> float:
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
