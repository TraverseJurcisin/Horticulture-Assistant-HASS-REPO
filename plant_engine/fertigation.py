"""Utility functions for fertigation calculations."""
from typing import Dict

from .nutrient_manager import get_recommended_levels


def recommend_fertigation_schedule(
    plant_type: str,
    stage: str,
    volume_l: float,
    purity: Dict[str, float],
) -> Dict[str, float]:
    """Return grams of fertilizer needed per nutrient for the solution volume."""
    targets = get_recommended_levels(plant_type, stage)
    schedule: Dict[str, float] = {}
    for nutrient, ppm in targets.items():
        mg = ppm * volume_l
        grams = mg / 1000
        fraction = purity.get(nutrient, 1.0)
        if fraction <= 0:
            raise ValueError(f"Purity for {nutrient} must be > 0")
        schedule[nutrient] = round(grams / fraction, 3)
    return schedule
