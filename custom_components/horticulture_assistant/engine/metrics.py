"""Common horticulture metric helpers."""

from __future__ import annotations

import math
from collections.abc import Sequence

import numpy as np

from ..calibration.fit import eval_model


def svp_kpa(t_c: float) -> float:
    """Saturation vapor pressure (kPa) using Magnus formula."""
    return 0.6108 * math.exp((17.27 * t_c) / (t_c + 237.3))


def vpd_kpa(t_c: float, rh_pct: float) -> float:
    """Vapor pressure deficit (kPa)."""
    rh = max(0.0, min(100.0, rh_pct)) / 100.0
    return round(svp_kpa(t_c) * (1.0 - rh), 3)


def dew_point_c(t_c: float, rh_pct: float) -> float:
    """Dew point in degrees Celsius."""
    a, b = 17.27, 237.3
    rh = max(1e-3, min(100.0, rh_pct)) / 100.0
    alpha = ((a * t_c) / (b + t_c)) + math.log(rh)
    return round((b * alpha) / (a - alpha), 2)


def humidity_from_dew_point(t_c: float, dew_point_c: float) -> float:
    """Relative humidity (%) from air and dew point temperatures."""
    if dew_point_c > t_c:
        raise ValueError("dew_point_c cannot exceed t_c")
    return round(100.0 * svp_kpa(dew_point_c) / svp_kpa(t_c), 1)


def lux_to_ppfd(lux: float, coeff: float = 0.0185) -> float:
    """Approximate PPFD (µmol m⁻² s⁻¹) from lux."""
    return max(0.0, lux) * coeff


def lux_model_ppfd(model: str, coeffs: Sequence[float], lux: float) -> float:
    """Convert lux to PPFD using a calibrated model."""

    return float(eval_model(model, list(coeffs), np.array([lux], dtype=float))[0])


def dli_from_ppfd(ppfd_umol_m2_s: float, seconds: float) -> float:
    """Convert PPFD over a period to daily light integral."""
    return (ppfd_umol_m2_s * seconds) / 1_000_000.0


def accumulate_dli(current: float, ppfd_umol_m2_s: float, seconds: float) -> float:
    """Accumulate DLI using PPFD over a period of time."""
    return current + dli_from_ppfd(ppfd_umol_m2_s, seconds)


def mold_risk(t_c: float, rh_pct: float) -> float:
    """Return an estimated mold risk on a 0..6 scale.

    The algorithm is adapted from common indoor gardening guidelines.  Risk
    increases with higher relative humidity and when the ambient temperature is
    close to the dew point.  Values are clamped to the 0..6 range and rounded to
    one decimal place for stable sensor readings.
    """

    dp = dew_point_c(t_c, rh_pct)
    proximity = max(0.0, 1.0 - (t_c - dp) / 5.0)
    if rh_pct < 70:
        base = 0.0
    elif rh_pct < 80:
        base = 1.0
    elif rh_pct < 90:
        base = 3.0
    else:
        base = 5.0
    risk = min(6.0, base + proximity * 2.0)
    return round(risk, 1)


def profile_status(mold: float | None, moisture_pct: float | None) -> str:
    """Classify plant health based on mold risk and moisture level."""

    status = "ok"
    if moisture_pct is not None:
        if moisture_pct < 10:
            return "critical"
        if moisture_pct < 20:
            status = "warn"
    if mold is not None:
        if mold >= 5:
            return "critical"
        if mold >= 3 and status == "ok":
            status = "warn"
    return status


__all__ = [
    "svp_kpa",
    "vpd_kpa",
    "dew_point_c",
    "lux_to_ppfd",
    "lux_model_ppfd",
    "dli_from_ppfd",
    "accumulate_dli",
    "mold_risk",
    "profile_status",
    "humidity_from_dew_point",
]
