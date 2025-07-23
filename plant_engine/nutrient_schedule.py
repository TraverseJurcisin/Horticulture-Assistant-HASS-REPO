"""Helpers to build daily nutrient uptake schedules."""

from typing import Dict, Mapping

from .growth_stage import list_growth_stages, get_stage_duration
from .irrigation_manager import get_daily_irrigation_target
from .fertigation import estimate_daily_nutrient_uptake

__all__ = ["generate_daily_uptake_plan"]


def generate_daily_uptake_plan(plant_type: str) -> Dict[str, Dict[int, Dict[str, float]]]:
    """Return daily nutrient uptake plan for the crop cycle.

    Parameters
    ----------
    plant_type : str
        Name of the plant type as defined in the datasets.

    Returns
    -------
    Dict[str, Dict[int, Dict[str, float]]]
        Mapping of stage name to a daily schedule. Each schedule maps the
        day number (starting at ``1``) to nutrient uptake values in
        milligrams per plant.
    """

    plan: Dict[str, Dict[int, Dict[str, float]]] = {}
    for stage in list_growth_stages(plant_type):
        duration = get_stage_duration(plant_type, stage)
        if not duration:
            continue
        daily_ml = get_daily_irrigation_target(plant_type, stage)
        daily_uptake = estimate_daily_nutrient_uptake(plant_type, stage, daily_ml)
        stage_plan: Dict[int, Dict[str, float]] = {}
        for day in range(1, duration + 1):
            stage_plan[day] = dict(daily_uptake)
        plan[stage] = stage_plan
    return plan
