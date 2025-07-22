"""Generate consolidated plant health reports."""
from __future__ import annotations

from typing import Mapping, Iterable, Dict

from . import (
    environment_manager,
    nutrient_manager,
    deficiency_manager,
    pest_manager,
    disease_manager,
    growth_stage,
)


def generate_health_report(
    plant_type: str,
    stage: str,
    env: Mapping[str, float],
    nutrient_levels: Mapping[str, float],
    *,
    pests: Iterable[str] = (),
    diseases: Iterable[str] = (),
) -> Dict[str, object]:
    """Return a consolidated health report for a plant.

    The report includes optimized environment data, nutrient deficiencies with
    symptoms, and recommended pest and disease treatments.
    """
    env_opt = environment_manager.optimize_environment(env, plant_type, stage)
    deficits = nutrient_manager.calculate_deficiencies(
        nutrient_levels, plant_type, stage
    )
    symptoms = deficiency_manager.diagnose_deficiencies(
        nutrient_levels, plant_type, stage
    )
    treatments = deficiency_manager.recommend_deficiency_treatments(
        nutrient_levels, plant_type, stage
    )
    pest_actions = pest_manager.recommend_treatments(plant_type, pests)
    disease_actions = disease_manager.recommend_treatments(plant_type, diseases)
    stage_info = growth_stage.get_stage_info(plant_type, stage)

    return {
        "environment": env_opt,
        "deficiencies": deficits,
        "symptoms": symptoms,
        "deficiency_treatments": treatments,
        "pest_actions": pest_actions,
        "disease_actions": disease_actions,
        "stage_info": stage_info,
    }

__all__ = ["generate_health_report"]

