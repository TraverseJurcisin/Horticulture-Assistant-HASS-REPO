"""Helpers to consolidate horticultural guidelines for plants."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from dataclasses import field as dataclass_field
from functools import cache
from typing import Any

from . import (
    bioinoculant_info,
    bioinoculant_manager,
    disease_manager,
    disease_monitor,
    ec_manager,
    environment_manager,
    growth_stage,
    height_manager,
    irrigation_manager,
    micro_manager,
    nutrient_manager,
    pest_manager,
    pest_monitor,
    ph_manager,
    stage_tasks,
    water_usage,
)

__all__ = ["GuidelineSummary", "get_guideline_summary"]


@dataclass
class GuidelineSummary:
    """Container for consolidated plant guideline data."""

    environment: dict[str, Any]
    nutrients: dict[str, float]
    micronutrients: dict[str, float]
    pest_guidelines: dict[str, str]
    disease_guidelines: dict[str, str]
    disease_prevention: dict[str, str]
    pest_prevention: dict[str, str] = dataclass_field(default_factory=dict)
    ipm_guidelines: dict[str, str] = dataclass_field(default_factory=dict)
    pest_thresholds: dict[str, int] = dataclass_field(default_factory=dict)
    disease_thresholds: dict[str, int] = dataclass_field(default_factory=dict)
    beneficial_insects: dict[str, list[str]] = dataclass_field(default_factory=dict)
    bioinoculants: list[str] = dataclass_field(default_factory=list)
    bioinoculant_details: dict[str, dict[str, str]] = dataclass_field(default_factory=dict)
    ph_range: list[float] = dataclass_field(default_factory=list)
    ec_range: list[float] = dataclass_field(default_factory=list)
    irrigation_volume_ml: float | None = None
    irrigation_interval_days: float | None = None
    pest_monitor_interval_days: int | None = None
    pest_sample_size: int | None = None
    disease_monitor_interval_days: int | None = None
    water_daily_ml: float | None = None
    stage_info: dict[str, Any] | None = None
    stages: list[str] | None = None
    stage_tasks: dict[str, list[str]] = dataclass_field(default_factory=dict)
    height_range: list[float] | None = None

    def as_dict(self) -> dict[str, Any]:
        """Return guidelines as a regular dictionary."""
        return asdict(self)


@cache
def get_guideline_summary(plant_type: str, stage: str | None = None) -> dict[str, Any]:
    """Return combined environment, nutrient and pest guidelines.

    The summary now also includes disease management, pH guidance,
    pest monitoring thresholds and beneficial insect suggestions for
    richer automation data.
    """

    thresholds = pest_monitor.get_pest_thresholds(plant_type, stage)
    beneficial = {p: pest_manager.get_beneficial_insects(p) for p in thresholds}
    disease_thresholds = disease_monitor.get_disease_thresholds(plant_type)
    pest_interval = pest_monitor.get_monitoring_interval(plant_type, stage)
    disease_interval = disease_monitor.get_monitoring_interval(plant_type, stage)

    if stage:
        tasks = {stage: stage_tasks.get_stage_tasks(plant_type, stage)}
    else:
        tasks = {
            s: stage_tasks.get_stage_tasks(plant_type, s)
            for s in growth_stage.list_growth_stages(plant_type)
        }

    inoculants = bioinoculant_manager.get_recommended_inoculants(plant_type)
    details = {name: bioinoculant_info.get_inoculant_info(name) for name in inoculants}

    height_rng = height_manager.get_height_range(plant_type, stage) if stage else None

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
        disease_thresholds=disease_thresholds,
        beneficial_insects=beneficial,
        bioinoculants=inoculants,
        bioinoculant_details=details,
        ph_range=ph_manager.get_ph_range(plant_type, stage),
        ec_range=list(ec_manager.get_ec_range(plant_type, stage) or []),
        irrigation_volume_ml=(
            irrigation_manager.get_daily_irrigation_target(plant_type, stage) if stage else None
        ),
        irrigation_interval_days=(
            irrigation_manager.get_recommended_interval(plant_type, stage) if stage else None
        ),
        pest_monitor_interval_days=pest_interval,
        pest_sample_size=pest_monitor.get_sample_size(plant_type),
        disease_monitor_interval_days=disease_interval,
        water_daily_ml=(water_usage.get_daily_use(plant_type, stage) if stage else None),
        stage_info=growth_stage.get_stage_info(plant_type, stage) if stage else None,
        stages=None if stage else growth_stage.list_growth_stages(plant_type),
        stage_tasks=tasks,
        height_range=list(height_rng) if height_rng else None,
    )

    return summary.as_dict()
