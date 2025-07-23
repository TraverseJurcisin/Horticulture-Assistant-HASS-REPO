"""High level nutrient profile analysis helpers."""
from __future__ import annotations

from typing import Dict, Mapping

from .nutrient_manager import (
    get_all_recommended_levels,
    calculate_all_deficiencies,
    calculate_all_surplus,
    calculate_nutrient_balance,
    get_stage_ratio,
)
from .nutrient_interactions import check_imbalances
from .toxicity_manager import check_toxicities

__all__ = ["analyze_nutrient_profile"]


def analyze_nutrient_profile(
    current_levels: Mapping[str, float], plant_type: str, stage: str
) -> Dict[str, object]:
    """Return holistic analysis for a nutrient solution."""

    recommended = get_all_recommended_levels(plant_type, stage)
    deficiencies = calculate_all_deficiencies(current_levels, plant_type, stage)
    surplus = calculate_all_surplus(current_levels, plant_type, stage)
    balance = calculate_nutrient_balance(current_levels, plant_type, stage)
    guideline_ratio = get_stage_ratio(plant_type, stage)

    def _calc_ratio(levels: Mapping[str, float]) -> Dict[str, float]:
        total = sum(float(levels.get(n, 0)) for n in ("N", "P", "K"))
        if total <= 0:
            return {"N": 0.0, "P": 0.0, "K": 0.0}
        return {k: round(levels.get(k, 0.0) / total, 2) for k in ("N", "P", "K")}

    current_ratio = _calc_ratio(current_levels)
    ratio_delta = {
        k: round(current_ratio.get(k, 0.0) - guideline_ratio.get(k, 0.0), 2)
        for k in ("N", "P", "K")
    }
    interactions = check_imbalances(current_levels)
    toxicity = check_toxicities(current_levels, plant_type)

    return {
        "recommended": recommended,
        "deficiencies": deficiencies,
        "surplus": surplus,
        "balance": balance,
        "interaction_warnings": interactions,
        "toxicities": toxicity,
        "ratio_guideline": guideline_ratio,
        "npk_ratio": current_ratio,
        "ratio_delta": ratio_delta,
    }

