"""Helpers for computing total nutrient requirements across a crop cycle."""
from __future__ import annotations

from typing import Dict

from plant_engine import growth_stage
from . import stage_nutrient_requirements

__all__ = ["calculate_cycle_totals"]


def calculate_cycle_totals(plant_type: str) -> Dict[str, float]:
    """Return cumulative nutrient requirements for the full growth cycle.

    The totals are derived from stage durations in :mod:`plant_engine.growth_stage`
    combined with per-stage daily requirements from
    :mod:`stage_nutrient_requirements`.
    """

    totals: Dict[str, float] = {}
    for stage in growth_stage.list_growth_stages(plant_type):
        days = growth_stage.get_stage_duration(plant_type, stage)
        if not days:
            continue
        daily = stage_nutrient_requirements.get_stage_requirements(plant_type, stage)
        for nutrient, value in daily.items():
            totals[nutrient] = round(totals.get(nutrient, 0.0) + value * days, 2)
    return totals
