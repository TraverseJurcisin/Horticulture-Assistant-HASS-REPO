"""Helpers to consolidate horticultural guidelines for plants."""

from __future__ import annotations

from dataclasses import dataclass, asdict, field as dataclass_field
from typing import Any, Dict, List, Optional

from functools import lru_cache
from . import (
    environment_manager,
    nutrient_manager,
    micro_manager,
    bioinoculant_manager,
    pest_manager,
    pest_monitor,
    disease_manager,
    ph_manager,
    ec_manager,
    irrigation_manager,
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
    pest_prevention: Dict[str, str] = dataclass_field(default_factory=dict)
    ipm_guidelines: Dict[str, str] = dataclass_field(default_factory=dict)
    pest_thresholds: Dict[str, int] = dataclass_field(default_factory=dict)
    beneficial_insects: Dict[str, list[str]] = dataclass_field(default_factory=dict)
    bioinoculants: List[str] = dataclass_field(default_factory=list)
    ph_range: List[float] = dataclass_field(default_factory=list)
    ec_range: List[float] = dataclass_field(default_factory=list)
    irrigation_volume_ml: float | None = None
    irrigation_interval_days: float | None = None
    stage_info: Optional[Dict[str, Any]] = None
    stages: Optional[List[str]] = None

    def as_dict(self) -> Dict[str, Any]:
        """Return guidelines as a regular dictionary."""
        return asdict(self)


@lru_cache(maxsize=None)
def get_guideline_summary(plant_type: str, stage: str | None = None) -> Dict[str, Any]:
    """Return combined environment, nutrient and pest guidelines.

    The summary now also includes disease management, pH guidance,
    pest monitoring thresholds and beneficial insect suggestions for
    richer automation data.
    """

    thresholds = pest_monitor.get_pest_thresholds(plant_type)
    beneficial = {p: pest_manager.get_beneficial_insects(p) for p in thresholds}

    summary = GuidelineSummary(
        environment=environment_manager.get_environmental_targets(plant_type, stage),
        nutrients=nutrient_manager.get_recommended_levels(plant_type, stage) if stage else {},
        micronutrients=micro_manager.get_recommended_levels(plant_type, stage) if stage else {},
        pest_guidelines=pest_manager.get_pest_guidelines(plant_type),
        pest_prevention=pest_manager.get_pest_prevention(plant_type),
        ipm_guidelines=pest_manager.get_ipm_guidelines(plant_type),
        disease_guidelines=disease_manager.get_disease_guidelines(plant_type),
        disease_prevention=disease_manager.get_disease_prevention(plant_type),
        pest_thresholds=thresholds,
        beneficial_insects=beneficial,
        bioinoculants=bioinoculant_manager.get_recommended_inoculants(plant_type),
        ph_range=ph_manager.get_ph_range(plant_type, stage),
        ec_range=list(ec_manager.get_ec_range(plant_type, stage) or []),
        irrigation_volume_ml=(
            irrigation_manager.get_daily_irrigation_target(plant_type, stage)
            if stage
            else None
        ),
        irrigation_interval_days=(
            irrigation_manager.get_recommended_interval(plant_type, stage)
            if stage
            else None
        ),
        stage_info=growth_stage.get_stage_info(plant_type, stage) if stage else None,
        stages=None if stage else growth_stage.list_growth_stages(plant_type),
    )

    return summary.as_dict()
