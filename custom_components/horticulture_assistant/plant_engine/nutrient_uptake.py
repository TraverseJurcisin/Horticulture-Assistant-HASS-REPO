"""Lookup daily nutrient uptake targets by plant type and stage."""
from __future__ import annotations

from typing import Dict

from .growth_stage import list_growth_stages, get_stage_duration
from .plant_density import get_spacing_cm

from .utils import load_dataset, list_dataset_entries

DATA_FILE = "nutrients/nutrient_uptake.json"

_DATA: Dict[str, Dict[str, Dict[str, float]]] = load_dataset(DATA_FILE)

__all__ = [
    "list_supported_plants",
    "get_daily_uptake",
    "estimate_stage_totals",
    "estimate_total_uptake",
    "estimate_cumulative_uptake",
    "estimate_average_daily_uptake",
    "get_uptake_ratio",
    "estimate_area_daily_uptake",
    "estimate_area_stage_uptake",
    "estimate_area_total_uptake",
    "estimate_area_cumulative_uptake",
]


def list_supported_plants() -> list[str]:
    """Return all plant types with uptake data."""
    return list_dataset_entries(_DATA)


def get_daily_uptake(plant_type: str, stage: str) -> Dict[str, float]:
    """Return mg/day uptake for ``plant_type`` and ``stage``."""
    plant = _DATA.get(plant_type.lower())
    if not plant:
        return {}
    return plant.get(stage.lower(), {})


def get_uptake_ratio(plant_type: str, stage: str) -> Dict[str, float]:
    """Return normalized N:P:K ratio from daily uptake data.

    The values sum to 1.0. Unknown plants or stages return an empty mapping.
    """

    daily = get_daily_uptake(plant_type, stage)
    n = daily.get("N", 0.0)
    p = daily.get("P", 0.0)
    k = daily.get("K", 0.0)
    total = n + p + k
    if total <= 0:
        return {}
    return {
        "N": round(n / total, 2),
        "P": round(p / total, 2),
        "K": round(k / total, 2),
    }


def estimate_stage_totals(plant_type: str, stage: str) -> Dict[str, float]:
    """Return total nutrient demand for a single stage in milligrams."""

    from .growth_stage import get_stage_duration

    duration = get_stage_duration(plant_type, stage)
    if not duration:
        return {}

    daily = get_daily_uptake(plant_type, stage)
    return {n: round(mg_per_day * duration, 2) for n, mg_per_day in daily.items()}


def estimate_total_uptake(plant_type: str) -> Dict[str, float]:
    """Return estimated nutrient use for the entire growth cycle."""

    from .growth_stage import list_growth_stages

    totals: Dict[str, float] = {}
    for stage in list_growth_stages(plant_type):
        stage_totals = estimate_stage_totals(plant_type, stage)
        for nutrient, mg in stage_totals.items():
            totals[nutrient] = round(totals.get(nutrient, 0.0) + mg, 2)
    return totals


def estimate_average_daily_uptake(plant_type: str) -> Dict[str, float]:
    """Return average daily nutrient demand for the full crop cycle."""

    totals = estimate_total_uptake(plant_type)
    if not totals:
        return {}

    from .growth_stage import get_total_cycle_duration

    days = get_total_cycle_duration(plant_type)
    if not days:
        return {}

    return {nutrient: round(mg / days, 2) for nutrient, mg in totals.items()}


def estimate_cumulative_uptake(plant_type: str, stage: str) -> Dict[str, float]:
    """Return total nutrient demand from the start through ``stage``."""

    stages = list_growth_stages(plant_type)
    if not stages or stage not in stages:
        return {}

    totals: Dict[str, float] = {}
    for st in stages:
        stage_totals = estimate_stage_totals(plant_type, st)
        for nutrient, amount in stage_totals.items():
            totals[nutrient] = round(totals.get(nutrient, 0.0) + amount, 2)
        if st == stage:
            break

    return totals


def estimate_area_daily_uptake(
    plant_type: str, stage: str, area_m2: float
) -> Dict[str, float]:
    """Return daily nutrient demand for ``area_m2`` of crop."""

    if area_m2 <= 0:
        raise ValueError("area_m2 must be positive")

    spacing = get_spacing_cm(plant_type)
    if spacing is None or spacing <= 0:
        return {}

    plants = area_m2 / ((spacing / 100) ** 2)
    daily = get_daily_uptake(plant_type, stage)
    return {n: round(val * plants, 2) for n, val in daily.items()}


def estimate_area_stage_uptake(
    plant_type: str, stage: str, area_m2: float
) -> Dict[str, float]:
    """Return total nutrient demand for an area during ``stage``."""

    daily_totals = estimate_area_daily_uptake(plant_type, stage, area_m2)
    if not daily_totals:
        return {}

    duration = get_stage_duration(plant_type, stage)
    if not duration:
        return {}

    return {n: round(val * duration, 2) for n, val in daily_totals.items()}


def estimate_area_total_uptake(plant_type: str, area_m2: float) -> Dict[str, float]:
    """Return nutrient demand for the entire crop cycle over ``area_m2``."""

    totals = estimate_total_uptake(plant_type)
    if not totals:
        return {}

    spacing = get_spacing_cm(plant_type)
    if spacing is None or spacing <= 0:
        return {}

    plants = area_m2 / ((spacing / 100) ** 2)
    return {n: round(val * plants, 2) for n, val in totals.items()}


def estimate_area_cumulative_uptake(
    plant_type: str, stage: str, area_m2: float
) -> Dict[str, float]:
    """Return cumulative nutrient demand up to ``stage`` over ``area_m2``."""

    totals = estimate_cumulative_uptake(plant_type, stage)
    if not totals:
        return {}

    spacing = get_spacing_cm(plant_type)
    if spacing is None or spacing <= 0:
        return {}

    plants = area_m2 / ((spacing / 100) ** 2)
    return {n: round(val * plants, 2) for n, val in totals.items()}
