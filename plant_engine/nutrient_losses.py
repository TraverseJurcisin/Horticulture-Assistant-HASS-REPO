"""Aggregate nutrient losses from leaching and volatilization."""
from __future__ import annotations

from typing import Dict, Mapping

from . import nutrient_leaching, nutrient_volatilization

__all__ = [
    "estimate_total_loss",
    "compensate_for_losses",
]


def estimate_total_loss(levels_mg: Mapping[str, float], plant_type: str | None = None) -> Dict[str, float]:
    """Return combined nutrient losses from leaching and volatilization."""
    leach = nutrient_leaching.estimate_leaching_loss(levels_mg, plant_type)
    vol = nutrient_volatilization.estimate_volatilization_loss(levels_mg, plant_type)

    losses: Dict[str, float] = {}
    for nutrient in set(levels_mg) | set(leach) | set(vol):
        losses[nutrient] = round(leach.get(nutrient, 0.0) + vol.get(nutrient, 0.0), 2)
    return losses


def compensate_for_losses(levels_mg: Mapping[str, float], plant_type: str | None = None) -> Dict[str, float]:
    """Return nutrient amounts adjusted for expected losses."""
    losses = estimate_total_loss(levels_mg, plant_type)
    adjusted: Dict[str, float] = {}
    for nutrient, mg in levels_mg.items():
        adjusted[nutrient] = round(float(mg) + losses.get(nutrient, 0.0), 2)
    return adjusted
