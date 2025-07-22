"""Lookup daily nutrient uptake targets by plant type and stage."""
from __future__ import annotations

from typing import Dict

from .growth_stage import get_stage_duration
from .utils import load_dataset, normalize_key

DATA_FILE = "nutrient_uptake.json"

_DATA: Dict[str, Dict[str, Dict[str, float]]] = load_dataset(DATA_FILE)

__all__ = [
    "list_supported_plants",
    "get_daily_uptake",
    "estimate_total_uptake",
]


def list_supported_plants() -> list[str]:
    """Return all plant types with uptake data."""
    return sorted(_DATA.keys())


def get_daily_uptake(plant_type: str, stage: str) -> Dict[str, float]:
    """Return mg/day nutrient uptake for ``plant_type`` and ``stage``."""

    plant = _DATA.get(normalize_key(plant_type))
    if not plant:
        return {}
    return plant.get(normalize_key(stage), {})


def estimate_total_uptake(plant_type: str) -> Dict[str, float]:
    """Return total nutrient uptake (mg) over the full growth cycle."""

    plant = _DATA.get(normalize_key(plant_type))
    if not plant:
        return {}

    totals: Dict[str, float] = {}
    for stage, daily in plant.items():
        days = get_stage_duration(plant_type, stage)
        if not days:
            continue
        for nutrient, mg_per_day in daily.items():
            totals[nutrient] = totals.get(nutrient, 0.0) + mg_per_day * days

    return {k: round(v, 2) for k, v in totals.items()}
