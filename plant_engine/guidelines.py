"""Helpers to consolidate dataset guidelines for a plant type."""

from __future__ import annotations

from typing import Any, Dict

from . import environment_manager, nutrient_manager, micro_manager, pest_manager, growth_stage

__all__ = ["get_guideline_summary"]


def get_guideline_summary(plant_type: str, stage: str | None = None) -> Dict[str, Any]:
    """Return combined environment, nutrient and pest guidelines.

    Parameters
    ----------
    plant_type : str
        Plant type used to look up guideline entries.
    stage : str, optional
        Growth stage for stage specific data.

    Returns
    -------
    Dict[str, Any]
        Dictionary with keys ``environment``, ``nutrients``, ``micronutrients``,
        ``pest_guidelines`` and either ``stage_info`` or ``stages`` when
        ``stage`` is not provided.
    """

    summary: Dict[str, Any] = {
        "environment": environment_manager.get_environmental_targets(plant_type, stage),
        "pest_guidelines": pest_manager.get_pest_guidelines(plant_type),
    }

    if stage:
        summary["nutrients"] = nutrient_manager.get_recommended_levels(plant_type, stage)
        summary["micronutrients"] = micro_manager.get_recommended_levels(plant_type, stage)
        summary["stage_info"] = growth_stage.get_stage_info(plant_type, stage)
    else:
        summary["nutrients"] = nutrient_manager.get_stage_guidelines(plant_type)
        summary["micronutrients"] = micro_manager.get_stage_guidelines(plant_type)
        summary["stages"] = growth_stage.list_growth_stages(plant_type)

    return summary
