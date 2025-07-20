"""Utilities for estimating plant water use via evapotranspiration."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Dict, Mapping

from plant_engine.et_model import calculate_et0, calculate_eta

# Conversion constant: 1 mm of water over 1 m^2 equals 1 liter (1000 mL)
MM_TO_ML_PER_M2 = 1000


@dataclass
class TranspirationMetrics:
    """Container for ET and transpiration calculations."""

    et0_mm_day: float
    eta_mm_day: float
    transpiration_ml_day: float

    def as_dict(self) -> Dict[str, float]:
        """Return metrics as a regular dictionary."""
        return asdict(self)

def compute_transpiration(plant_profile: Mapping, env_data: Mapping) -> Dict[str, float]:
    """Return evapotranspiration metrics for a single plant profile."""

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
    ml_per_day = mm_per_day * MM_TO_ML_PER_M2 * canopy_m2

    metrics = TranspirationMetrics(
        et0_mm_day=et0,
        eta_mm_day=et_actual,
        transpiration_ml_day=round(ml_per_day, 1),
    )

    return metrics.as_dict()

