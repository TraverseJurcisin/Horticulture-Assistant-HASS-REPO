"""Simple helpers for nutrient adjustment calculations."""

from __future__ import annotations

from collections.abc import Mapping

from ..engine.plant_engine.nutrient_manager import calculate_nutrient_adjustments

__all__ = ["recommend_adjustments", "ppm_to_mg"]


def recommend_adjustments(
    current_levels: Mapping[str, float],
    plant_type: str,
    stage: str,
    volume_l: float | None = None,
) -> dict[str, float]:
    """Return nutrient ppm adjustments and optional milligram totals.

    Parameters
    ----------
    current_levels: Mapping[str, float]
        Current measured nutrient values in ppm.
    plant_type: str
        Crop identifier for guideline lookup.
    stage: str
        Growth stage for guideline lookup.
    volume_l: float | None
        Optional solution volume. If provided the returned dictionary
        includes additional ``*_mg`` keys with the milligram amounts to
        add to that volume.
    """

    ppm_adjust = calculate_nutrient_adjustments(current_levels, plant_type, stage)
    if volume_l is None or not ppm_adjust:
        return ppm_adjust

    mg_adjust: dict[str, float] = {}
    for nutrient, ppm in ppm_adjust.items():
        mg_adjust[f"{nutrient}_mg"] = ppm * volume_l
    ppm_adjust.update(mg_adjust)
    return ppm_adjust


def ppm_to_mg(ppm: float, volume_l: float) -> float:
    """Return milligrams represented by ``ppm`` in ``volume_l`` liters."""
    return round(ppm * volume_l, 3)
