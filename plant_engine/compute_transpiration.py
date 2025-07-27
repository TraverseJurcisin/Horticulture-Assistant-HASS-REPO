"""Utilities for estimating plant water use via evapotranspiration."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from functools import lru_cache
from typing import Dict, Mapping, Iterable

import pandas as pd

from .utils import load_dataset, normalize_key
from .constants import DEFAULT_ENV
from .canopy import estimate_canopy_area

MODIFIER_FILE = "crop_coefficient_modifiers.json"
# cached via load_dataset
_MODIFIERS: Dict[str, Dict[str, float]] = load_dataset(MODIFIER_FILE)

from plant_engine.et_model import calculate_et0, calculate_eta

DATA_FILE = "crop_coefficients.json"
# cached via load_dataset
_KC_DATA: Dict[str, Dict[str, float]] = load_dataset(DATA_FILE)

# Public API
__all__ = [
    "TranspirationMetrics",
    "adjust_crop_coefficient",
    "lookup_crop_coefficient",
    "compute_transpiration",
    "compute_transpiration_series",
    "compute_transpiration_dataframe",
]
# Conversion constant: 1 mm of water over 1 m^2 equals 1 liter (1000 mL)
MM_TO_ML_PER_M2 = 1000


@dataclass(slots=True)
class TranspirationMetrics:
    """Container for ET and transpiration calculations."""

    et0_mm_day: float
    eta_mm_day: float
    transpiration_ml_day: float

    def as_dict(self) -> Dict[str, float]:
        """Return metrics as a regular dictionary."""
        return asdict(self)


def adjust_crop_coefficient(
    kc: float, temp_c: float | None, rh_pct: float | None
) -> float:
    """Return KC adjusted for temperature and humidity."""
    result = kc

    humidity = _MODIFIERS.get("humidity", {})
    if rh_pct is not None:
        low_t = humidity.get("low_threshold")
        high_t = humidity.get("high_threshold")
        if low_t is not None and rh_pct < low_t:
            result *= humidity.get("low_factor", 1.0)
        if high_t is not None and rh_pct > high_t:
            result *= humidity.get("high_factor", 1.0)

    temp = _MODIFIERS.get("temperature", {})
    if temp_c is not None:
        low_t = temp.get("low_threshold")
        high_t = temp.get("high_threshold")
        if low_t is not None and temp_c < low_t:
            result *= temp.get("low_factor", 1.0)
        if high_t is not None and temp_c > high_t:
            result *= temp.get("high_factor", 1.0)

    return float(result)


@lru_cache(maxsize=None)
def lookup_crop_coefficient(plant_type: str, stage: str | None = None) -> float:
    """Return crop coefficient for ``plant_type`` and ``stage``.

    Results are cached to avoid repeated dataset lookups.
    """
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

    kc = adjust_crop_coefficient(kc, env.get("temp_c"), env.get("rh_pct"))
    et_actual = calculate_eta(et0, kc)

    canopy_m2 = plant_profile.get("canopy_m2")
    if canopy_m2 is None:
        canopy_m2 = estimate_canopy_area(
            plant_profile.get("plant_type"), plant_profile.get("stage")
        )
    mm_per_day = et_actual
    ml_per_day = mm_per_day * MM_TO_ML_PER_M2 * canopy_m2

    metrics = TranspirationMetrics(
        et0_mm_day=et0,
        eta_mm_day=et_actual,
        transpiration_ml_day=round(ml_per_day, 1),
    )

    return metrics.as_dict()


def compute_transpiration_series(
    plant_profile: Mapping,
    env_series: Iterable[Mapping],
    weights: Iterable[float] | None = None,
) -> Dict[str, float]:
    """Return weighted average transpiration metrics for ``env_series``.

    Parameters
    ----------
    plant_profile : Mapping
        Plant profile dictionary used for each reading.
    env_series : Iterable[Mapping]
        Sequence of environment readings.
    weights : Iterable[float] | None, optional
        Weights applied to each reading when averaging. If provided, the
        length must match ``env_series``. Non-positive weights are ignored.
    """

    env_list = list(env_series)
    if weights is None:
        weight_list = [1.0] * len(env_list)
    else:
        weight_list = list(weights)
        if len(weight_list) != len(env_list):
            raise ValueError("weights length must match env_series length")

    total_w = 0.0
    total_et0 = 0.0
    total_eta = 0.0
    total_ml = 0.0

    for env, w in zip(env_list, weight_list):
        if w <= 0:
            continue
        metrics = compute_transpiration(plant_profile, env)
        total_et0 += metrics["et0_mm_day"] * w
        total_eta += metrics["eta_mm_day"] * w
        total_ml += metrics["transpiration_ml_day"] * w
        total_w += w

    if total_w == 0:
        return TranspirationMetrics(0.0, 0.0, 0.0).as_dict()

    return TranspirationMetrics(
        round(total_et0 / total_w, 2),
        round(total_eta / total_w, 2),
        round(total_ml / total_w, 1),
    ).as_dict()


def compute_transpiration_dataframe(
    plant_profile: Mapping, env_df: pd.DataFrame
) -> pd.DataFrame:
    """Return transpiration metrics for each row in ``env_df``.

    The input DataFrame should contain the same columns accepted by
    :func:`compute_transpiration`. The resulting DataFrame shares the
    same index.
    """

    if not isinstance(env_df, pd.DataFrame):
        raise TypeError("env_df must be a pandas DataFrame")

    metrics = [
        compute_transpiration(plant_profile, row)
        for row in env_df.to_dict(orient="records")
    ]
    return pd.DataFrame(metrics, index=env_df.index)

