"""High level nutrient management recommendations."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Dict, Optional

from .nutrient_analysis import analyze_nutrient_profile, NutrientAnalysis
from .fertigation import recommend_correction_schedule

__all__ = ["NutrientManagementReport", "generate_nutrient_management_report"]


@dataclass(slots=True)
class NutrientManagementReport:
    """Combined nutrient analysis and correction schedule."""

    analysis: NutrientAnalysis
    corrections_g: Dict[str, float]


def generate_nutrient_management_report(
    current_levels: Mapping[str, float],
    plant_type: str,
    stage: str,
    volume_l: float,
    *,
    purity: Mapping[str, float] | None = None,
    product: str | None = None,
) -> NutrientManagementReport:
    """Return holistic nutrient report with correction grams.

    Parameters
    ----------
    current_levels : Mapping[str, float]
        Measured nutrient solution in ppm.
    plant_type : str
        Crop identifier for guideline lookup.
    stage : str
        Growth stage for guideline lookup.
    volume_l : float
        Solution volume in liters used to compute corrections.
    purity : Mapping[str, float], optional
        Purity fractions per nutrient. Overrides values from ``product``.
    product : str, optional
        Fertilizer product identifier for purity lookup.
    """

    analysis = analyze_nutrient_profile(current_levels, plant_type, stage)
    corrections = recommend_correction_schedule(
        current_levels,
        plant_type,
        stage,
        volume_l,
        purity,
        product=product,
    )
    return NutrientManagementReport(analysis=analysis, corrections_g=corrections)
