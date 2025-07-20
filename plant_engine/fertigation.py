"""Utility functions for fertigation calculations."""
from __future__ import annotations

from typing import Dict, Mapping

from .nutrient_manager import calculate_deficiencies, get_recommended_levels


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


def recommend_correction_schedule(
    current_levels: Mapping[str, float],
    plant_type: str,
    stage: str,
    volume_l: float,
    purity: Mapping[str, float],
) -> Dict[str, float]:
    """Return grams required to correct observed deficiencies."""
    deficits = calculate_deficiencies(current_levels, plant_type, stage)
    corrections: Dict[str, float] = {}
    for nutrient, ppm in deficits.items():
        mg = ppm * volume_l
        grams = mg / 1000
        frac = purity.get(nutrient, 1.0)
        if frac <= 0:
            raise ValueError(f"Purity for {nutrient} must be > 0")
        corrections[nutrient] = round(grams / frac, 3)
    return corrections
