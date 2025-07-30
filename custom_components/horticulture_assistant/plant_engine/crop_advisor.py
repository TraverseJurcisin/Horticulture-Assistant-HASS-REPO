from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Iterable, Dict

from .environment_manager import recommend_environment_adjustments
from .nutrient_planner import generate_nutrient_management_report, NutrientManagementReport
from .pest_manager import build_pest_management_plan

__all__ = ["CropAdvice", "generate_crop_advice"]


@dataclass(slots=True)
class CropAdvice:
    """Aggregated management recommendations for a crop."""

    environment: Dict[str, str]
    nutrients: NutrientManagementReport
    pests: Dict[str, Any]


def generate_crop_advice(
    current_environment: Mapping[str, float],
    nutrient_levels: Mapping[str, float],
    pests: Iterable[str],
    plant_type: str,
    stage: str,
    volume_l: float,
    *,
    zone: str | None = None,
) -> CropAdvice:
    """Return combined environment, nutrient and pest recommendations."""

    env_actions = recommend_environment_adjustments(
        current_environment, plant_type, stage, zone
    )
    nutrient_report = generate_nutrient_management_report(
        nutrient_levels, plant_type, stage, volume_l
    )
    pest_plan = build_pest_management_plan(plant_type, pests)

    return CropAdvice(
        environment=env_actions,
        nutrients=nutrient_report,
        pests=pest_plan,
    )
