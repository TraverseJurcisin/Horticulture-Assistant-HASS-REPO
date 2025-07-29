"""Helpers for cost-optimized nutrient mix generation."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any, Mapping

from plant_engine.nutrient_manager import get_environment_adjusted_levels
from plant_engine.fertigation import _schedule_from_totals


@dataclass(slots=True)
class OptimizedMix:
    """Container for an optimized fertigation recommendation."""

    schedule: Dict[str, float]
    cost: float
    diagnostics: Dict[str, Any]

    def as_dict(self) -> Dict[str, Any]:
        """Return a plain dictionary representation."""
        return {
            "schedule": self.schedule,
            "cost": self.cost,
            "diagnostics": self.diagnostics,
        }


# Default fertilizer mapping aligned with bundled price data
DEFAULT_FERTILIZERS = {
    "N": "foxfarm_grow_big",
    "P": "foxfarm_grow_big",
    "K": "intrepid_granular_potash_0_0_60",
}


def _compute_totals(targets: Mapping[str, float], volume_l: float) -> Dict[str, float]:
    """Return total nutrient mass (mg) for ppm targets."""
    return {nut: ppm * volume_l for nut, ppm in targets.items()}


def optimize_mix(
    plant_type: str,
    stage: str,
    volume_l: float,
    *,
    ph: float | None = None,
    root_temp_c: float | None = None,
    use_synergy: bool = False,
    fertilizers: Mapping[str, str] | None = None,
    purity_overrides: Mapping[str, float] | None = None,
) -> OptimizedMix:
    """Return fertigation plan adjusted for environment conditions."""

    targets = get_environment_adjusted_levels(
        plant_type,
        stage,
        ph=ph,
        root_temp_c=root_temp_c,
        synergy=use_synergy,
    )
    if not targets:
        return OptimizedMix({}, 0.0, {})

    totals = _compute_totals(targets, volume_l)
    ferts = fertilizers or DEFAULT_FERTILIZERS
    schedule = _schedule_from_totals(totals, 1, ferts, purity_overrides)

    from custom_components.horticulture_assistant.fertilizer_formulator import estimate_mix_cost

    cost = estimate_mix_cost(schedule)
    diagnostics = {
        "targets_ppm": targets,
        "volume_l": volume_l,
    }
    return OptimizedMix(schedule, cost, diagnostics)


__all__ = ["optimize_mix", "OptimizedMix"]
