"""High level nutrient management recommendations."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from custom_components.horticulture_assistant.fertilizer_formulator import (
    get_cheapest_product,
)

from .fertigation import recommend_correction_schedule
from .nutrient_analysis import NutrientAnalysis, analyze_nutrient_profile

__all__ = [
    "NutrientManagementReport",
    "NutrientManagementCostReport",
    "generate_nutrient_management_report",
    "generate_nutrient_management_report_with_cost",
]


@dataclass(slots=True)
class NutrientManagementReport:
    """Combined nutrient analysis and correction schedule."""

    analysis: NutrientAnalysis
    corrections_g: dict[str, float]


@dataclass(slots=True)
class NutrientManagementCostReport(NutrientManagementReport):
    """Extends :class:`NutrientManagementReport` with cost information."""

    cost_total: float
    cost_breakdown: dict[str, float]


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
        Must be a positive value.
    purity : Mapping[str, float], optional
        Purity fractions per nutrient. Overrides values from ``product``.
    product : str, optional
        Fertilizer product identifier for purity lookup.
    """

    if volume_l <= 0:
        raise ValueError("volume_l must be positive")

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


def _estimate_correction_cost(corrections: Mapping[str, float]) -> tuple[float, dict[str, float]]:
    """Return total cost and per-nutrient breakdown for ``corrections``."""

    total = 0.0
    breakdown: dict[str, float] = {}
    for nutrient, grams in corrections.items():
        if grams <= 0:
            continue
        try:
            _pid, cost_per_g = get_cheapest_product(nutrient)
        except Exception:
            continue
        cost = round(grams * cost_per_g, 2)
        breakdown[nutrient] = cost
        total += cost
    return round(total, 2), breakdown


def generate_nutrient_management_report_with_cost(
    current_levels: Mapping[str, float],
    plant_type: str,
    stage: str,
    volume_l: float,
    *,
    purity: Mapping[str, float] | None = None,
    product: str | None = None,
) -> NutrientManagementCostReport:
    """Return nutrient report with correction grams and estimated costs."""

    base = generate_nutrient_management_report(
        current_levels,
        plant_type,
        stage,
        volume_l,
        purity=purity,
        product=product,
    )

    total, breakdown = _estimate_correction_cost(base.corrections_g)
    return NutrientManagementCostReport(
        analysis=base.analysis,
        corrections_g=base.corrections_g,
        cost_total=total,
        cost_breakdown=breakdown,
    )
