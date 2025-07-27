"""Helpers for generating fertigation plans from plant profiles."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Mapping, Dict, Any

try:
    from homeassistant.core import HomeAssistant
except Exception:  # pragma: no cover - Home Assistant not available during tests
    HomeAssistant = None  # type: ignore

from .plant_profile_loader import load_profile_by_id
from .path_utils import plants_path
from plant_engine.fertigation import recommend_precise_fertigation

_LOGGER = logging.getLogger(__name__)


@dataclass
class FertigationPlan:
    """Structured fertigation recommendation."""

    schedule: Dict[str, float]
    cost_total: float
    cost_breakdown: Dict[str, float]
    warnings: Dict[str, Dict[str, float]]
    diagnostics: Dict[str, Dict[str, float]]

    def as_dict(self) -> Dict[str, Any]:
        return {
            "schedule": self.schedule,
            "cost_total": self.cost_total,
            "cost_breakdown": self.cost_breakdown,
            "warnings": self.warnings,
            "diagnostics": self.diagnostics,
        }


def plan_fertigation_from_profile(
    plant_id: str,
    volume_l: float,
    hass: HomeAssistant | None = None,
    *,
    water_profile: Mapping[str, float] | None = None,
    include_micro: bool = False,
    fertilizers: Mapping[str, str] | None = None,
) -> FertigationPlan:
    """Return a fertigation plan using profile data and dataset guidelines."""

    if volume_l <= 0:
        raise ValueError("volume_l must be positive")

    base_dir = plants_path(hass)
    profile = load_profile_by_id(plant_id, base_dir)
    if not profile:
        _LOGGER.warning("Profile for %s not found", plant_id)
        return FertigationPlan({}, 0.0, {}, {}, {})

    general = profile.get("general", {})
    plant_type = general.get("plant_type")
    stage = (
        general.get("lifecycle_stage")
        or general.get("stage")
        or profile.get("stage")
    )
    if not plant_type or not stage:
        _LOGGER.warning("Incomplete profile for %s", plant_id)
        return FertigationPlan({}, 0.0, {}, {}, {})

    if fertilizers is None:
        fertilizers = {
            "N": "foxfarm_grow_big",
            "P": "foxfarm_grow_big",
            "K": "intrepid_granular_potash_0_0_60",
        }

    schedule, total, breakdown, warnings, diagnostics = recommend_precise_fertigation(
        plant_type,
        stage,
        volume_l,
        water_profile,
        fertilizers=fertilizers,
        include_micro=include_micro,
    )

    return FertigationPlan(schedule, total, breakdown, warnings, diagnostics)


__all__ = ["plan_fertigation_from_profile", "FertigationPlan"]
