"""Transpiration calculation utilities."""
from __future__ import annotations

from typing import Dict, Mapping

from plant_engine.et_model import calculate_et0, calculate_eta

def compute_transpiration(plant_profile: Mapping, env_data: Mapping) -> Dict:
    """
    Calculate ET₀, ETₐ, and estimated daily water use (mL/day) for a single plant.
    Returns a dictionary with values to inject into sensors.
    """

    et0 = calculate_et0(
        temperature_c=env_data["temp_c"],
        rh_percent=env_data["rh_pct"],
        solar_rad_w_m2=env_data.get("par_w_m2", env_data.get("par", 0)),
        wind_m_s=env_data.get("wind_speed_m_s", 1.0),
        elevation_m=env_data.get("elevation_m", 200)
    )

    kc = plant_profile.get("kc", 1.0)
    et_actual = calculate_eta(et0, kc)

    canopy_m2 = plant_profile.get("canopy_m2", 0.25)
    mm_per_day = et_actual
    ml_per_day = mm_per_day * 1000 * canopy_m2  # mm * m² = L = *1000 → mL

    return {
        "et0_mm_day": et0,
        "eta_mm_day": et_actual,
        "transpiration_ml_day": round(ml_per_day, 1)
    }
