"""Helpers for irrigation scheduling."""
from __future__ import annotations

from typing import Optional

from .rootzone_model import RootZone

__all__ = [
    "recommend_irrigation_volume",
    "recommend_irrigation_interval",
]


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
    max_add = rootzone.total_available_water_ml - available_ml
    required = min(required, max_add)
    return round(max(required, 0.0), 1)


def recommend_irrigation_interval(
    rootzone: RootZone,
    available_ml: float,
    expected_et_ml_day: float,
) -> float:
    """Return days until irrigation is required based on ET rate.

    ``available_ml`` is the current water volume in the root zone. The function
    estimates how many days of evapotranspiration it will take for the soil
    moisture to drop to the readily available level. ``expected_et_ml_day`` must
    be positive.
    """

    if expected_et_ml_day <= 0:
        raise ValueError("expected_et_ml_day must be positive")
    if available_ml < 0:
        raise ValueError("available_ml must be non-negative")

    depletion = available_ml - rootzone.readily_available_water_ml
    if depletion <= 0:
        return 0.0

    days = depletion / expected_et_ml_day
    return round(max(days, 0.0), 2)
