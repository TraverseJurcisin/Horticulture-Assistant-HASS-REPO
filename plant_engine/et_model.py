"""Evapotranspiration model and reference lookups."""

import math
from functools import lru_cache
from typing import Optional

import numpy as np
import pandas as pd

from .utils import load_dataset, normalize_key

def calculate_et0(
    temperature_c: float,
    rh_percent: float,
    solar_rad_w_m2: float,
    wind_m_s: Optional[float] = 1.0,
    elevation_m: Optional[float] = 200
) -> float:
    """
    Calculate ET₀ (reference evapotranspiration) using the FAO-56 Penman-Monteith equation approximation.
    Based on air temp, RH, solar radiation, wind, elevation.
    Returns ET₀ in mm/day.
    """

    # Convert solar radiation to MJ/m²/day
    solar_rad_mj = solar_rad_w_m2 * 0.0864

    # Psychrometric constant (kPa/°C)
    gamma = 0.665e-3 * (101.3 * ((293 - 0.0065 * elevation_m) / 293)**5.26)

    # Saturation vapor pressure (kPa)
    es = 0.6108 * math.exp((17.27 * temperature_c) / (temperature_c + 237.3))

    # Actual vapor pressure
    ea = es * (rh_percent / 100)

    # Slope of vapor pressure curve (Δ) (kPa/°C)
    delta = 4098 * es / ((temperature_c + 237.3)**2)

    # Net radiation estimate (assuming albedo 0.23)
    rn = 0.77 * solar_rad_mj  # MJ/m²/day

    # ET₀ estimate
    et0 = (
        (0.408 * delta * rn) +
        (gamma * 900 * wind_m_s * (es - ea) / (temperature_c + 273))
    ) / (delta + gamma * (1 + 0.34 * wind_m_s))

    return round(et0, 2)  # mm/day


def calculate_eta(et0: float, kc: float = 1.0) -> float:
    """Calculate Actual Evapotranspiration based on Kc coefficient."""
    return round(et0 * kc, 2)


def calculate_et0_series(
    temperature_c: "pd.Series",
    rh_percent: "pd.Series",
    solar_rad_w_m2: "pd.Series",
    wind_m_s: "pd.Series | float" = 1.0,
    elevation_m: "pd.Series | float" = 200,
) -> "pd.Series":
    """Vectorized ET₀ calculation for pandas Series."""

    temp = pd.Series(temperature_c, dtype=float)
    rh = pd.Series(rh_percent, dtype=float)
    solar = pd.Series(solar_rad_w_m2, dtype=float)
    if isinstance(wind_m_s, pd.Series):
        wind = wind_m_s.astype(float)
    else:
        wind = pd.Series(float(wind_m_s), index=temp.index)
    if isinstance(elevation_m, pd.Series):
        elevation = elevation_m.astype(float)
    else:
        elevation = pd.Series(float(elevation_m), index=temp.index)

    solar_rad_mj = solar * 0.0864
    gamma = 0.665e-3 * (
        101.3 * ((293 - 0.0065 * elevation) / 293) ** 5.26
    )
    es = 0.6108 * np.exp((17.27 * temp) / (temp + 237.3))
    ea = es * (rh / 100)
    delta = 4098 * es / ((temp + 237.3) ** 2)
    rn = 0.77 * solar_rad_mj
    et0 = (
        (0.408 * delta * rn)
        + (gamma * 900 * wind * (es - ea) / (temp + 273))
    ) / (delta + gamma * (1 + 0.34 * wind))
    return et0.round(2)


ET0_DATA_FILE = "et0/reference_et0.json"
ET0_RANGE_FILE = "et0/reference_et0_range.json"
ET0_CLIMATE_FILE = "et0/et0_climate_adjustments.json"


@lru_cache(maxsize=None)
def get_reference_et0(month: int) -> float | None:
    """Return typical reference ET₀ for the given month if known."""

    if not 1 <= month <= 12:
        raise ValueError("month must be between 1 and 12")

    data = load_dataset(ET0_DATA_FILE)
    value = data.get(str(month))
    return float(value) if isinstance(value, (int, float)) else None


@lru_cache(maxsize=None)
def get_reference_et0_range(month: int) -> tuple[float, float] | None:
    """Return (min, max) ET₀ for ``month`` if available."""

    if not 1 <= month <= 12:
        raise ValueError("month must be between 1 and 12")

    data = load_dataset(ET0_RANGE_FILE)
    value = data.get(str(month))
    if (
        isinstance(value, (list, tuple))
        and len(value) >= 2
        and all(isinstance(v, (int, float)) for v in value[:2])
    ):
        low, high = float(value[0]), float(value[1])
        return (low, high) if low <= high else (high, low)
    return None


@lru_cache(maxsize=None)
def get_et0_climate_adjustment(zone: str) -> float:
    """Return ET₀ multiplier for a climate ``zone`` if defined."""

    data = load_dataset(ET0_CLIMATE_FILE)
    value = data.get(normalize_key(zone))
    try:
        return float(value) if value is not None else 1.0
    except (TypeError, ValueError):
        return 1.0


def adjust_et0_for_climate(et0: float, zone: str | None) -> float:
    """Return ET₀ adjusted using the climate zone multiplier."""

    if zone:
        factor = get_et0_climate_adjustment(zone)
    else:
        factor = 1.0
    return round(et0 * factor, 2)


__all__ = [
    "calculate_et0",
    "calculate_eta",
    "calculate_et0_series",
    "get_reference_et0",
    "get_reference_et0_range",
    "get_et0_climate_adjustment",
    "adjust_et0_for_climate",
    "estimate_stage_et",
]


def estimate_stage_et(plant_type: str, stage: str, month: int) -> float:
    """Return estimated daily ET for a crop stage and month.

    This helper combines :data:`reference_et0.json` with
    :data:`crop_coefficients.json` to provide a simple lookup based on
    typical conditions when detailed environment readings are not
    available. ``0.0`` is returned if any value is missing.
    """

    et0 = get_reference_et0(month)
    if et0 is None:
        return 0.0

    kc_data = load_dataset("coefficients/crop_coefficients.json")
    plant = kc_data.get(normalize_key(plant_type))
    if not isinstance(plant, dict):
        return 0.0
    kc = plant.get(normalize_key(stage))
    if kc is None:
        kc = plant.get("default")
    if kc is None:
        return 0.0

    try:
        kc_val = float(kc)
    except (TypeError, ValueError):
        return 0.0

    return calculate_eta(et0, kc_val)

