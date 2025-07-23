"""Utilities for estimating plant water use via evapotranspiration."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Dict, Mapping, Iterable

from .utils import load_dataset, normalize_key
from .constants import DEFAULT_ENV

from plant_engine.et_model import calculate_et0, calculate_eta

DATA_FILE = "crop_coefficients.json"
# cached via load_dataset
_KC_DATA: Dict[str, Dict[str, float]] = load_dataset(DATA_FILE)

# Public API
__all__ = [
    "TranspirationMetrics",
    "lookup_crop_coefficient",
    "compute_transpiration",
    "compute_transpiration_series",
]
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


def lookup_crop_coefficient(plant_type: str, stage: str | None = None) -> float:
    """Return Kc value from :data:`crop_coefficients.json` or ``1.0``."""
    plant = _KC_DATA.get(normalize_key(plant_type))
    if not plant:
        return 1.0
    if stage:
        kc = plant.get(normalize_key(stage))
        if kc is not None:
            return float(kc)
    return float(plant.get("default", 1.0))

def compute_transpiration(plant_profile: Mapping, env_data: Mapping) -> Dict[str, float]:
    """Return evapotranspiration metrics for a single plant profile.

    Missing environment values fall back to :data:`DEFAULT_ENV` so callers can
    provide partial readings without raising ``KeyError``.
    """

    env = {**DEFAULT_ENV, **env_data}

    et0 = calculate_et0(
        temperature_c=env["temp_c"],
        rh_percent=env["rh_pct"],
        solar_rad_w_m2=env.get("par_w_m2", env.get("par", 0)),
        wind_m_s=env.get("wind_speed_m_s", 1.0),
        elevation_m=env.get("elevation_m", 200),
    )

    kc = plant_profile.get("kc")
    if kc is None:
        plant_type = plant_profile.get("plant_type")
        stage = plant_profile.get("stage")
        if plant_type:
            kc = lookup_crop_coefficient(plant_type, stage)
        else:
            kc = 1.0
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


def compute_transpiration_series(
    plant_profile: Mapping, env_series: Iterable[Mapping]
) -> Dict[str, float]:
    """Return averaged transpiration metrics for a sequence of readings."""

    total_et0 = 0.0
    total_eta = 0.0
    total_ml = 0.0
    count = 0

    for env in env_series:
        metrics = compute_transpiration(plant_profile, env)
        total_et0 += metrics["et0_mm_day"]
        total_eta += metrics["eta_mm_day"]
        total_ml += metrics["transpiration_ml_day"]
        count += 1

    if count == 0:
        return TranspirationMetrics(0.0, 0.0, 0.0).as_dict()

    return TranspirationMetrics(
        round(total_et0 / count, 2),
        round(total_eta / count, 2),
        round(total_ml / count, 1),
    ).as_dict()

