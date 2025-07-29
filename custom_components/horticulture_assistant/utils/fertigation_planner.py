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
from plant_engine.fertigation import (
    recommend_precise_fertigation,
    get_fertigation_volume,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class FertigationPlan:
    """Structured fertigation recommendation returned by
    :func:`plan_fertigation_from_profile`.

    All numeric values use litres and ppm for easy integration with other
    modules.  ``schedule`` maps nutrient names to the required mass of each
    fertilizer in grams.
    """

    schedule: Dict[str, float]
    cost_total: float
    cost_breakdown: Dict[str, float]
    warnings: Dict[str, Dict[str, float]]
    diagnostics: Dict[str, Dict[str, float]]

    def as_dict(self) -> Dict[str, Any]:
        """Return the plan as a plain serialisable dictionary."""
        return {
            "schedule": self.schedule,
            "cost_total": self.cost_total,
            "cost_breakdown": self.cost_breakdown,
            "warnings": self.warnings,
            "diagnostics": self.diagnostics,
        }


def _extract_plant_info(profile: Mapping[str, Any]) -> tuple[str | None, str | None]:
    """Return ``(plant_type, stage)`` from a loaded profile."""

    general = profile.get("general", {}) if isinstance(profile, Mapping) else {}
    plant_type = general.get("plant_type")
    stage = general.get("lifecycle_stage") or general.get("stage") or profile.get("stage")
    return (
        str(plant_type).lower() if plant_type is not None else None,
        str(stage).lower() if stage is not None else None,
    )


def plan_fertigation_from_profile(
    plant_id: str,
    volume_l: float | None = None,
    hass: HomeAssistant | None = None,
    *,
    water_profile: Mapping[str, float] | None = None,
    include_micro: bool = False,
    fertilizers: Mapping[str, str] | None = None,
    use_synergy: bool = False,
) -> FertigationPlan:
    """Return a fertigation plan using profile data and dataset guidelines.

    When ``volume_l`` is ``None`` the value is looked up in the
    :data:`fertigation_volume.json` dataset via
    :func:`plant_engine.fertigation.get_fertigation_volume`.
    """

    if volume_l is not None and volume_l <= 0:
        raise ValueError("volume_l must be positive")

    base_dir = plants_path(hass)
    profile = load_profile_by_id(plant_id, base_dir)
    if not profile:
        _LOGGER.warning("Profile for %s not found", plant_id)
        return FertigationPlan({}, 0.0, {}, {}, {})

    plant_type, stage = _extract_plant_info(profile)
    if not plant_type or not stage:
        _LOGGER.warning("Incomplete profile for %s", plant_id)
        return FertigationPlan({}, 0.0, {}, {}, {})

    if volume_l is None:
        vol_ml = get_fertigation_volume(plant_type, stage)
        if vol_ml is None:
            _LOGGER.warning(
                "No fertigation volume guideline for %s at %s stage",
                plant_type,
                stage,
            )
            return FertigationPlan({}, 0.0, {}, {}, {})
        volume_l = vol_ml / 1000

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
        use_synergy=use_synergy,
    )

    return FertigationPlan(schedule, total, breakdown, warnings, diagnostics)


__all__ = ["plan_fertigation_from_profile", "FertigationPlan"]
