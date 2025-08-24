"""High level fertigation planning utilities."""

from __future__ import annotations

from typing import Any

from .fertigation import (
    get_fertigation_interval,
    recommend_loss_adjusted_fertigation,
)

__all__ = ["generate_fertigation_plan"]


def generate_fertigation_plan(plant_type: str, stage: str, volume_l: float) -> dict[str, Any]:
    """Return fertigation schedule and interval for a plant stage.

    The schedule is loss-adjusted using dataset factors and includes an
    estimated cost breakdown. Interval days are looked up via
    :data:`fertigation_intervals.json`. The return dictionary contains:

    ``schedule_g`` - grams of each fertilizer per batch
    ``cost`` - estimated total cost
    ``cost_breakdown`` - cost per fertilizer
    ``warnings`` - warnings from formulation checks
    ``diagnostics`` - nutrient ppm and toxicity diagnostics
    ``interval_days`` - recommended days between fertigation events
    """

    schedule, cost, breakdown, warnings, diagnostics = recommend_loss_adjusted_fertigation(
        plant_type, stage, volume_l
    )

    interval = get_fertigation_interval(plant_type, stage)

    return {
        "schedule_g": schedule,
        "cost": cost,
        "cost_breakdown": breakdown,
        "warnings": warnings,
        "diagnostics": diagnostics,
        "interval_days": interval,
    }
