"""Helpers to generate nutrient schedules across growth stages."""

from __future__ import annotations

from dataclasses import dataclass
from functools import cache

try:  # Home Assistant add-on bundle ships a vendored plant_engine package.
    from plant_engine import growth_stage
except ImportError:  # pragma: no cover - fallback for test/dev environments
    from ..engine.plant_engine import growth_stage

from custom_components.horticulture_assistant.utils import stage_nutrient_requirements


@dataclass(slots=True)
class StageNutrientTotals:
    stage: str
    duration_days: int
    totals: dict[str, float]


@cache
def generate_nutrient_schedule(plant_type: str) -> list[StageNutrientTotals]:
    """Return per-stage nutrient totals for ``plant_type``.

    The schedule is computed from :mod:`stage_nutrient_requirements` and
    :mod:`plant_engine.growth_stage` data. Each stage entry includes the
    duration in days and total nutrient requirement amounts in milligrams.
    Unknown stages or missing data are skipped gracefully.
    """

    schedule: list[StageNutrientTotals] = []
    for stage in growth_stage.list_growth_stages(plant_type):
        duration = growth_stage.get_stage_duration(plant_type, stage)
        if not duration:
            continue
        daily = stage_nutrient_requirements.get_stage_requirements(plant_type, stage)
        totals = {nut: round(val * duration, 2) for nut, val in daily.items()}
        schedule.append(StageNutrientTotals(stage, duration, totals))
    return schedule


__all__ = ["StageNutrientTotals", "generate_nutrient_schedule"]
