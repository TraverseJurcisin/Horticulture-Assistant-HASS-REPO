"""Common horticulture metric helpers."""

from __future__ import annotations

import math


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


def lux_to_ppfd(lux: float, coeff: float = 0.0185) -> float:
    """Approximate PPFD (µmol m⁻² s⁻¹) from lux."""
    return max(0.0, lux) * coeff


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


__all__ = [
    "svp_kpa",
    "vpd_kpa",
    "dew_point_c",
    "lux_to_ppfd",
    "dli_from_ppfd",
    "accumulate_dli",
    "mold_risk",
]
