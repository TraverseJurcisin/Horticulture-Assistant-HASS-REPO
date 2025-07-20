"""Helpers for irrigation scheduling."""
from __future__ import annotations

from typing import Optional

from .rootzone_model import RootZone

__all__ = ["recommend_irrigation_volume"]


def recommend_irrigation_volume(
    rootzone: RootZone,
    available_ml: float,
    expected_et_ml: float,
    *,
    refill_to_full: bool = True,
) -> float:
    """Return irrigation volume needed to maintain root zone moisture.

    Parameters
    ----------
    rootzone : RootZone
        Water holding model for the plant.
    available_ml : float
        Current available water volume in milliliters.
    expected_et_ml : float
        Expected evapotranspiration loss before next irrigation.
    refill_to_full : bool, optional
        When ``True`` the zone is filled back to field capacity; otherwise only
        enough water to reach the readily available level is recommended.
    """
    projected = available_ml - expected_et_ml
    if projected >= rootzone.readily_available_water_ml:
        return 0.0

    target = rootzone.total_available_water_ml if refill_to_full else rootzone.readily_available_water_ml
    required = target - projected
    return round(max(required, 0.0), 1)
