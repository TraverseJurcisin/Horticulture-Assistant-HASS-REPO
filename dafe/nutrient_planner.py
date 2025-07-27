"""Utility functions for nutrient scheduling using dataset recommendations."""

from __future__ import annotations

from typing import Dict

from plant_engine.nutrient_manager import get_recommended_levels

__all__ = ["get_stage_targets", "calculate_daily_nutrient_mass"]


def get_stage_targets(plant_type: str, stage: str) -> Dict[str, float]:
    """Return recommended nutrient ppm targets for ``plant_type`` and ``stage``."""
    return get_recommended_levels(plant_type, stage)


def calculate_daily_nutrient_mass(
    plant_type: str,
    stage: str,
    water_ml: float,
) -> Dict[str, float]:
    """Return nutrient mass requirements in milligrams for a daily irrigation.

    Parameters
    ----------
    plant_type : str
        Name of the crop as found in the nutrient guidelines dataset.
    stage : str
        Growth stage key within the dataset for ``plant_type``.
    water_ml : float
        Daily irrigation volume in milliliters.
    """
    levels = get_stage_targets(plant_type, stage)
    volume_l = water_ml / 1000.0
    return {nut: round(ppm * volume_l, 3) for nut, ppm in levels.items()}
