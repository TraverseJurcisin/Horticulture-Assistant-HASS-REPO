"""Helpers for irrigation scheduling."""
from __future__ import annotations

from typing import Optional

from .utils import load_dataset, normalize_key
from .et_model import calculate_eta

from .rootzone_model import RootZone

__all__ = [
    "recommend_irrigation_volume",
    "recommend_irrigation_interval",
    "get_crop_coefficient",
    "estimate_irrigation_demand",
    "plan_irrigation",
]

_KC_DATA_FILE = "crop_coefficients.json"
_KC_DATA = load_dataset(_KC_DATA_FILE)


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


def get_crop_coefficient(plant_type: str, stage: str) -> float:
    """Return crop coefficient for ``plant_type`` and ``stage``."""
    coeffs = _KC_DATA.get(normalize_key(plant_type), {})
    return coeffs.get(normalize_key(stage), 1.0)


def estimate_irrigation_demand(
    plant_type: str,
    stage: str,
    et0_mm_day: float,
    area_m2: float = 1.0,
) -> float:
    """Return daily irrigation volume in liters.

    Parameters
    ----------
    plant_type : str
        Plant type used to look up the crop coefficient.
    stage : str
        Growth stage for the coefficient lookup.
    et0_mm_day : float
        Reference ET in millimeters per day.
    area_m2 : float, optional
        Plant canopy area in square meters. 1 mm over 1 m² equals 1 L.
    """
    if et0_mm_day < 0:
        raise ValueError("et0_mm_day must be non-negative")
    if area_m2 <= 0:
        raise ValueError("area_m2 must be positive")

    kc = get_crop_coefficient(plant_type, stage)
    eta_mm = calculate_eta(et0_mm_day, kc)
    liters = eta_mm * area_m2
    return round(liters, 2)


def plan_irrigation(
    plant_type: str,
    stage: str,
    et0_mm_day: float,
    rootzone: RootZone,
    available_ml: float,
    *,
    area_m2: Optional[float] = None,
    days: int = 1,
) -> dict:
    """Return recommended irrigation volume and interval.

    Parameters
    ----------
    plant_type : str
        Plant type for crop coefficient lookup.
    stage : str
        Growth stage for the coefficient lookup.
    et0_mm_day : float
        Reference ET in millimeters per day.
    rootzone : RootZone
        Root zone model for the plant.
    available_ml : float
        Current available water volume in the root zone.
    area_m2 : float, optional
        Canopy area in square meters. Defaults to the area derived from
        ``rootzone`` when omitted.
    days : int, optional
        Number of days to plan for when refilling to field capacity.
    """

    if days <= 0:
        raise ValueError("days must be positive")

    if area_m2 is None:
        if rootzone.root_depth_cm <= 0:
            area_m2 = 1.0
        else:
            area_m2 = rootzone.root_volume_cm3 / rootzone.root_depth_cm / 10000

    daily_liters = estimate_irrigation_demand(plant_type, stage, et0_mm_day, area_m2)
    expected_et_ml = daily_liters * 1000 * days

    volume_ml = recommend_irrigation_volume(
        rootzone, available_ml, expected_et_ml, refill_to_full=True
    )

    interval_days = recommend_irrigation_interval(
        rootzone, available_ml, daily_liters * 1000
    )

    return {
        "volume_ml": volume_ml,
        "interval_days": interval_days,
    }
