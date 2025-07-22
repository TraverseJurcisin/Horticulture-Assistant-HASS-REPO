"""High level nutrient profile analysis helpers."""
from __future__ import annotations

from typing import Dict, Mapping

from .nutrient_manager import (
    get_all_recommended_levels,
    calculate_all_deficiencies,
    calculate_all_surplus,
    calculate_nutrient_balance,
)
from .nutrient_interactions import check_imbalances

__all__ = ["analyze_nutrient_profile"]


def analyze_nutrient_profile(
    current_levels: Mapping[str, float], plant_type: str, stage: str
) -> Dict[str, object]:
    """Return holistic analysis for a nutrient solution."""

    recommended = get_all_recommended_levels(plant_type, stage)
    deficiencies = calculate_all_deficiencies(current_levels, plant_type, stage)
    surplus = calculate_all_surplus(current_levels, plant_type, stage)
    balance = calculate_nutrient_balance(current_levels, plant_type, stage)
    interactions = check_imbalances(current_levels)

    return {
        "recommended": recommended,
        "deficiencies": deficiencies,
        "surplus": surplus,
        "balance": balance,
        "interaction_warnings": interactions,
    }

