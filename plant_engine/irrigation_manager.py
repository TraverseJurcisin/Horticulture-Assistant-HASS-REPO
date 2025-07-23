"""Helpers for irrigation scheduling."""
from __future__ import annotations

from typing import Mapping, Dict

from .utils import load_dataset, normalize_key
from .et_model import calculate_eta

from .rootzone_model import RootZone, calculate_remaining_water

__all__ = [
    "recommend_irrigation_volume",
    "recommend_irrigation_interval",
    "get_crop_coefficient",
    "estimate_irrigation_demand",
    "recommend_irrigation_from_environment",
    "list_supported_plants",
    "get_daily_irrigation_target",
    "generate_irrigation_schedule",
]

_KC_DATA_FILE = "crop_coefficients.json"
_KC_DATA = load_dataset(_KC_DATA_FILE)

_IRRIGATION_FILE = "irrigation_guidelines.json"
_IRRIGATION_DATA: Dict[str, Dict[str, float]] = load_dataset(_IRRIGATION_FILE)


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
    if expected_et_ml < 0:
        raise ValueError("expected_et_ml must be non-negative")
    if available_ml < 0:
        raise ValueError("available_ml must be non-negative")

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


def recommend_irrigation_from_environment(
    plant_profile: Mapping[str, float],
    env_data: Mapping[str, float],
    rootzone: RootZone,
    available_ml: float,
    *,
    refill_to_full: bool = True,
) -> Dict[str, object]:
    """Return irrigation volume using transpiration estimated from ``env_data``.

    This helper bridges :func:`compute_transpiration` and
    :func:`recommend_irrigation_volume` so automations can directly pass current
    environment readings and receive both the evapotranspiration metrics and the
    irrigation volume recommendation in one call.
    """

    from .compute_transpiration import compute_transpiration

    metrics = compute_transpiration(plant_profile, env_data)
    volume = recommend_irrigation_volume(
        rootzone, available_ml, metrics["transpiration_ml_day"], refill_to_full=refill_to_full
    )

    return {
        "volume_ml": volume,
        "metrics": metrics,
    }


def list_supported_plants() -> list[str]:
    """Return plant types with irrigation guidelines."""

    return sorted(_IRRIGATION_DATA.keys())


def get_daily_irrigation_target(plant_type: str, stage: str) -> float:
    """Return recommended daily irrigation volume in milliliters."""

    plant = _IRRIGATION_DATA.get(normalize_key(plant_type), {})
    value = plant.get(normalize_key(stage))
    return float(value) if isinstance(value, (int, float)) else 0.0


def generate_irrigation_schedule(
    rootzone: RootZone,
    available_ml: float,
    et_ml_series: Mapping[int, float] | list[float],
    *,
    refill_to_full: bool = True,
) -> Dict[int, float]:
    """Return daily irrigation volumes to maintain root zone moisture.

    ``et_ml_series`` should contain expected evapotranspiration loss for each
    day in milliliters. The function simulates soil moisture over the period and
    calls :func:`recommend_irrigation_volume` for each day, accounting for
    irrigation applied on previous days.
    """

    if available_ml < 0:
        raise ValueError("available_ml must be non-negative")
    if any(v < 0 for v in et_ml_series):
        raise ValueError("et_ml_series values must be non-negative")

    schedule: Dict[int, float] = {}
    remaining = float(available_ml)
    for day, et_ml in enumerate(et_ml_series, start=1):
        volume = recommend_irrigation_volume(
            rootzone, remaining, et_ml, refill_to_full=refill_to_full
        )
        schedule[day] = volume
        remaining = calculate_remaining_water(
            rootzone, remaining, irrigation_ml=volume, et_ml=et_ml
        )

    return schedule
