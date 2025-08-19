"""Utilities for estimating plant water use via evapotranspiration."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from functools import lru_cache
from typing import Dict, Iterable, Mapping

import numpy as np
import pandas as pd

from .utils import load_dataset, normalize_key
from .constants import DEFAULT_ENV
from .canopy import estimate_canopy_area

MODIFIER_FILE = "coefficients/crop_coefficient_modifiers.json"
# cached via load_dataset
_MODIFIERS: Dict[str, Dict[str, float]] = load_dataset(MODIFIER_FILE)

from .et_model import (
    calculate_et0,
    calculate_eta,
    calculate_et0_series,
)

DATA_FILE = "coefficients/crop_coefficients.json"
# cached via load_dataset
_KC_DATA: Dict[str, Dict[str, float]] = load_dataset(DATA_FILE)

# Public API
__all__ = [
    "TranspirationMetrics",
    "adjust_crop_coefficient",
    "lookup_crop_coefficient",
    "compute_transpiration",
    "compute_transpiration_series",
    "compute_weighted_transpiration_dataframe",
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

    ``env_data`` may contain aliases such as ``temperature`` or ``humidity``
    which are normalized using :func:`environment_manager.normalize_environment_readings`.
    Missing environment values fall back to :data:`DEFAULT_ENV` so callers can
    provide partial readings without raising ``KeyError``.
    """

    from .environment_manager import normalize_environment_readings

    env = normalize_environment_readings(env_data)
    if "humidity_pct" in env and "rh_pct" not in env:
        env["rh_pct"] = env.pop("humidity_pct")
    if "light_ppfd" in env and "par_w_m2" not in env:
        env["par_w_m2"] = env.pop("light_ppfd")

    env = {**DEFAULT_ENV, **env}

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
    env_series: Iterable[Mapping] | pd.DataFrame,
    weights: Iterable[float] | pd.Series | None = None,
) -> Dict[str, float]:
    """Return weighted average transpiration metrics for ``env_series``.

    ``env_series`` is converted to a :class:`~pandas.DataFrame` and processed
    in bulk for efficiency. When ``weights`` are provided they must match the
    length of ``env_series``. Non‑positive weights are ignored in the final
    average.
    """

    if isinstance(env_series, pd.DataFrame):
        df = env_series
    else:
        df = pd.DataFrame(list(env_series))
    if df.empty:
        return TranspirationMetrics(0.0, 0.0, 0.0).as_dict()

    return compute_weighted_transpiration_dataframe(
        plant_profile, df, weights
    )


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

    df = env_df.copy()
    for key, default in DEFAULT_ENV.items():
        if key not in df:
            df[key] = default
        else:
            df[key] = df[key].fillna(default)

    kc = plant_profile.get("kc")
    if kc is None:
        plant_type = plant_profile.get("plant_type")
        stage = plant_profile.get("stage")
        kc = lookup_crop_coefficient(plant_type or "", stage) if plant_type else 1.0

    # Vectorised adjustment of the crop coefficient using the modifier dataset
    humidity = _MODIFIERS.get("humidity", {})
    kc_series = pd.Series(float(kc), index=df.index)
    low_t = humidity.get("low_threshold")
    if low_t is not None:
        kc_series = np.where(df["rh_pct"] < low_t, kc_series * humidity.get("low_factor", 1.0), kc_series)
    high_t = humidity.get("high_threshold")
    if high_t is not None:
        kc_series = np.where(df["rh_pct"] > high_t, kc_series * humidity.get("high_factor", 1.0), kc_series)

    temp_mod = _MODIFIERS.get("temperature", {})
    low_t = temp_mod.get("low_threshold")
    if low_t is not None:
        kc_series = np.where(df["temp_c"] < low_t, kc_series * temp_mod.get("low_factor", 1.0), kc_series)
    high_t = temp_mod.get("high_threshold")
    if high_t is not None:
        kc_series = np.where(df["temp_c"] > high_t, kc_series * temp_mod.get("high_factor", 1.0), kc_series)

    et0 = calculate_et0_series(
        df["temp_c"],
        df["rh_pct"],
        df["par_w_m2"],
        df.get("wind_speed_m_s", 1.0),
        df.get("elevation_m", 200),
    )

    eta = (et0 * kc_series).round(2)

    canopy = plant_profile.get("canopy_m2")
    if canopy is None:
        canopy = estimate_canopy_area(
            plant_profile.get("plant_type"), plant_profile.get("stage")
        )

    transp_ml = (eta * MM_TO_ML_PER_M2 * canopy).round(1)

    return pd.DataFrame(
        {
            "et0_mm_day": et0,
            "eta_mm_day": eta,
            "transpiration_ml_day": transp_ml,
        },
        index=env_df.index,
    )


def compute_weighted_transpiration_dataframe(
    plant_profile: Mapping,
    env_df: pd.DataFrame,
    weights: Iterable[float] | pd.Series | None = None,
) -> Dict[str, float]:
    """Return weighted average metrics for ``env_df``.

    Parameters
    ----------
    plant_profile : Mapping
        Plant profile containing crop coefficient and canopy information.
    env_df : pandas.DataFrame
        Environment readings with the same columns accepted by
        :func:`compute_transpiration_dataframe`.
    weights : iterable of float or pandas.Series, optional
        Weights for each row when averaging. Non-positive weights are ignored.
    """

    metrics = compute_transpiration_dataframe(plant_profile, env_df)

    if weights is None:
        weights_arr = np.ones(len(metrics))
    else:
        weights_arr = np.asarray(list(weights), dtype=float)
        if len(weights_arr) != len(metrics):
            raise ValueError("weights length must match env_df length")

    weights_arr = np.where(weights_arr > 0, weights_arr, 0)
    total_w = weights_arr.sum()
    if total_w == 0:
        return TranspirationMetrics(0.0, 0.0, 0.0).as_dict()

    weighted = metrics.mul(weights_arr, axis=0).sum() / total_w
    return TranspirationMetrics(
        round(float(weighted["et0_mm_day"]), 2),
        round(float(weighted["eta_mm_day"]), 2),
        round(float(weighted["transpiration_ml_day"]), 1),
    ).as_dict()
