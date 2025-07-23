"""Lookup daily water use estimates for irrigation planning."""
from __future__ import annotations

from typing import Dict

from .utils import load_dataset, normalize_key, list_dataset_entries

DATA_FILE = "water_usage_guidelines.json"

_DATA: Dict[str, Dict[str, float]] = load_dataset(DATA_FILE)

from .plant_density import get_spacing_cm
from .growth_stage import list_growth_stages, get_stage_duration

__all__ = [
    "list_supported_plants",
    "get_daily_use",
    "estimate_area_use",
    "estimate_cycle_use",
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


def estimate_cycle_use(plant_type: str, area_m2: float = 1.0) -> float:
    """Return estimated water use for a full crop cycle in liters.

    The estimate multiplies the per-plant daily usage for each growth stage
    by its expected duration from :mod:`plant_engine.growth_stage` and the
    number of plants that fit into ``area_m2`` based on recommended spacing.

    Parameters
    ----------
    plant_type : str
        Identifier used to look up spacing, stage durations and water usage.
    area_m2 : float, optional
        Cultivation area in square meters. Defaults to ``1.0``.

    Returns
    -------
    float
        Total water requirement in liters rounded to two decimals. Unknown
        plant types result in ``0.0``. ``ValueError`` is raised when
        ``area_m2`` is not positive.
    """

    if area_m2 <= 0:
        raise ValueError("area_m2 must be positive")

    spacing_cm = get_spacing_cm(plant_type)
    if spacing_cm is None or spacing_cm <= 0:
        return 0.0

    plants = area_m2 / ((spacing_cm / 100) ** 2)
    total_ml = 0.0

    for stage in list_growth_stages(plant_type):
        days = get_stage_duration(plant_type, stage)
        if not days:
            continue
        daily = get_daily_use(plant_type, stage)
        total_ml += days * daily

    return round(total_ml * plants / 1000, 2)
