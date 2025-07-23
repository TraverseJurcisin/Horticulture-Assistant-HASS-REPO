"""Lookup daily water use estimates for irrigation planning."""
from __future__ import annotations

from typing import Dict

from .utils import load_dataset, normalize_key, list_dataset_entries

DATA_FILE = "water_usage_guidelines.json"

_DATA: Dict[str, Dict[str, float]] = load_dataset(DATA_FILE)

from .plant_density import get_spacing_cm

__all__ = [
    "list_supported_plants",
    "get_daily_use",
    "estimate_area_use",
    "estimate_total_use",
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

    The calculation multiplies per‑plant usage by the estimated plant count
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


def estimate_total_use(
    plant_type: str, stage: str, area_m2: float, days: int
) -> float:
    """Return cumulative water use in milliliters.

    Parameters
    ----------
    plant_type : str
        Crop identifier used for dataset lookups.
    stage : str
        Growth stage for daily use calculations.
    area_m2 : float
        Crop surface area in square meters. Must be positive.
    days : int
        Number of days to estimate. Must be positive.
    """
    if days <= 0:
        raise ValueError("days must be positive")

    daily_ml = estimate_area_use(plant_type, stage, area_m2)
    return round(daily_ml * days, 1)
