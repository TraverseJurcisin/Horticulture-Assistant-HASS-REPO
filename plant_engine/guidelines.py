"""Helpers to consolidate horticultural guidelines for plants."""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional

from . import (
    environment_manager,
    nutrient_manager,
    micro_manager,
    pest_manager,
    disease_manager,
    ph_manager,
    growth_stage,
)

__all__ = ["GuidelineSummary", "get_guideline_summary"]


@dataclass
class GuidelineSummary:
    """Container for consolidated plant guideline data."""

    environment: Dict[str, Any]
    nutrients: Dict[str, float]
    micronutrients: Dict[str, float]
    pest_guidelines: Dict[str, str]
    disease_guidelines: Dict[str, str]
    disease_prevention: Dict[str, str]
    ph_range: List[float]
    stage_info: Optional[Dict[str, Any]] = None
    stages: Optional[List[str]] = None

    def as_dict(self) -> Dict[str, Any]:
        """Return guidelines as a regular dictionary."""
        return asdict(self)


def get_guideline_summary(plant_type: str, stage: str | None = None) -> Dict[str, Any]:
    """Return combined environment, nutrient and pest guidelines.

    The summary now also includes disease management and pH guidance for
    richer automation data.
    """

    summary = GuidelineSummary(
        environment=environment_manager.get_environmental_targets(plant_type, stage),
        nutrients=nutrient_manager.get_recommended_levels(plant_type, stage) if stage else {},
        micronutrients=micro_manager.get_recommended_levels(plant_type, stage) if stage else {},
        pest_guidelines=pest_manager.get_pest_guidelines(plant_type),
        disease_guidelines=disease_manager.get_disease_guidelines(plant_type),
        disease_prevention=disease_manager.get_disease_prevention(plant_type),
        ph_range=ph_manager.get_ph_range(plant_type, stage),
        stage_info=growth_stage.get_stage_info(plant_type, stage) if stage else None,
        stages=None if stage else growth_stage.list_growth_stages(plant_type),
    )

    return summary.as_dict()
