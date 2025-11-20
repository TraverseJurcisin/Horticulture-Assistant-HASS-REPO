"""Generate consolidated plant health reports."""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from . import (deficiency_manager, disease_manager, environment_manager,
               growth_stage, nutrient_interactions, nutrient_manager,
               pest_manager, stage_tasks)


def generate_health_report(
    plant_type: str,
    stage: str,
    env: Mapping[str, float],
    nutrient_levels: Mapping[str, float],
    *,
    pests: Iterable[str] = (),
    diseases: Iterable[str] = (),
    water_test: Mapping[str, float] | None = None,
) -> dict[str, object]:
    """Return a consolidated health report for a plant.

    The report includes optimized environment data, nutrient deficiencies with
    symptoms, recommended pest and disease treatments and optional water quality
    information.
    """
    env_opt = environment_manager.optimize_environment(
        env, plant_type, stage, water_test=water_test
    )
    deficits = nutrient_manager.calculate_deficiencies(nutrient_levels, plant_type, stage)
    symptoms = deficiency_manager.diagnose_deficiencies(nutrient_levels, plant_type, stage)
    treatments = deficiency_manager.recommend_deficiency_treatments(
        nutrient_levels, plant_type, stage
    )
    imbalances = nutrient_interactions.check_imbalances(nutrient_levels)
    pest_actions = pest_manager.recommend_treatments(plant_type, pests)
    disease_actions = disease_manager.recommend_treatments(plant_type, diseases)
    stage_info = growth_stage.get_stage_info(plant_type, stage)
    tasks = stage_tasks.get_stage_tasks(plant_type, stage)

    return {
        "environment": env_opt,
        "deficiencies": deficits,
        "symptoms": symptoms,
        "deficiency_treatments": treatments,
        "nutrient_imbalances": imbalances,
        "pest_actions": pest_actions,
        "disease_actions": disease_actions,
        "stage_info": stage_info,
        "stage_tasks": tasks,
    }


__all__ = ["generate_health_report"]
