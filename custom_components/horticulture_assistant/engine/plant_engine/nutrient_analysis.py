"""High level nutrient profile analysis helpers."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass

from .nutrient_interactions import check_imbalances
from .nutrient_manager import (calculate_all_deficiencies,
                               calculate_all_surplus,
                               calculate_nutrient_balance,
                               get_all_recommended_levels, get_stage_ratio)
from .toxicity_manager import check_toxicities

__all__ = ["NutrientAnalysis", "analyze_nutrient_profile"]


@dataclass(slots=True)
class NutrientAnalysis:
    """Detailed nutrient profile analysis results."""

    recommended: dict[str, float]
    deficiencies: dict[str, float]
    surplus: dict[str, float]
    balance: dict[str, float]
    interaction_warnings: dict[str, str]
    toxicities: dict[str, str]
    ratio_guideline: dict[str, float]
    npk_ratio: dict[str, float]
    ratio_delta: dict[str, float]

    def as_dict(self) -> dict[str, object]:
        """Return the analysis as a regular dictionary."""
        return asdict(self)


def analyze_nutrient_profile(
    current_levels: Mapping[str, float], plant_type: str, stage: str
) -> NutrientAnalysis:
    """Return holistic analysis for a nutrient solution."""

    recommended = get_all_recommended_levels(plant_type, stage)
    deficiencies = calculate_all_deficiencies(current_levels, plant_type, stage)
    surplus = calculate_all_surplus(current_levels, plant_type, stage)
    balance = calculate_nutrient_balance(current_levels, plant_type, stage)
    guideline_ratio = get_stage_ratio(plant_type, stage)

    def _calc_ratio(levels: Mapping[str, float]) -> dict[str, float]:
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

    return NutrientAnalysis(
        recommended=recommended,
        deficiencies=deficiencies,
        surplus=surplus,
        balance=balance,
        interaction_warnings=interactions,
        toxicities=toxicity,
        ratio_guideline=guideline_ratio,
        npk_ratio=current_ratio,
        ratio_delta=ratio_delta,
    )
