import math
from typing import Optional, Dict

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
