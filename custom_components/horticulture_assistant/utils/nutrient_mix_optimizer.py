"""Helpers for cost-optimized nutrient mix generation."""

from __future__ import annotations

"""Helpers for computing cost optimised fertigation mixes."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from plant_engine.fertigation import _schedule_from_totals
from plant_engine.nutrient_manager import get_environment_adjusted_levels


@dataclass(slots=True)
class OptimizedMix:
    """Container for an optimized fertigation recommendation."""

    schedule: dict[str, float]
    cost: float
    diagnostics: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
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


def _compute_totals(targets: Mapping[str, float], volume_l: float) -> dict[str, float]:
    """Return total nutrient mass (mg) for ``volume_l`` of solution."""

    return {nut: ppm * volume_l for nut, ppm in targets.items()}


def optimize_mix(
    plant_type: str,
    stage: str,
    volume_l: float,
    *,
    num_plants: int = 1,
    ph: float | None = None,
    root_temp_c: float | None = None,
    use_synergy: bool = False,
    fertilizers: Mapping[str, str] | None = None,
    purity_overrides: Mapping[str, float] | None = None,
) -> OptimizedMix:
    """Return optimized fertigation schedule and estimated cost.

    Parameters
    ----------
    plant_type : str
        Crop identifier used for guideline lookup.
    stage : str
        Growth stage name (e.g. ``"vegetative"``).
    volume_l : float
        Total solution volume in liters. Must be positive.
    num_plants : int, optional
        Number of plants the solution is shared between. Defaults to ``1``.
    ph : float, optional
        Current nutrient solution pH used for adjustments.
    root_temp_c : float, optional
        Root zone temperature in Celsius for adjustment.
    use_synergy : bool, optional
        When ``True`` nutrient synergy factors are applied.
    fertilizers : Mapping[str, str] | None, optional
        Mapping of nutrient code to fertilizer identifier. Defaults to
        :data:`DEFAULT_FERTILIZERS`.
    purity_overrides : Mapping[str, float] | None, optional
        Override nutrient purity fractions when provided.
    """

    if volume_l <= 0:
        raise ValueError("volume_l must be positive")
    if num_plants <= 0:
        raise ValueError("num_plants must be positive")

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
    schedule = _schedule_from_totals(totals, num_plants, ferts, purity_overrides)

    from custom_components.horticulture_assistant.fertilizer_formulator import estimate_mix_cost

    cost = estimate_mix_cost(schedule)
    diagnostics = {
        "targets_ppm": targets,
        "volume_l": volume_l,
        "num_plants": num_plants,
    }
    return OptimizedMix(schedule, cost, diagnostics)


__all__ = ["optimize_mix", "OptimizedMix"]
