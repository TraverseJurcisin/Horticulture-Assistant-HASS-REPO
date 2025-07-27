"""Root zone temperature impact on nutrient uptake."""
from __future__ import annotations

from bisect import bisect_left
from typing import Mapping, Dict, Sequence

from .utils import load_dataset

DATA_FILE = "root_temperature_uptake.json"

_DATA = load_dataset(DATA_FILE)
_TEMPS: Sequence[float] = [float(t) for t in _DATA.get("temperature_c", [])]
_FACTORS: Sequence[float] = [float(f) for f in _DATA.get("factor", [])]

__all__ = [
    "get_uptake_factor",
    "adjust_uptake",
]


def get_uptake_factor(temp_c: float) -> float:
    """Return uptake efficiency factor for ``temp_c`` in Celsius."""
    if not _TEMPS or len(_TEMPS) != len(_FACTORS):
        return 1.0
    idx = bisect_left(_TEMPS, temp_c)
    if idx <= 0:
        return float(_FACTORS[0])
    if idx >= len(_TEMPS):
        return float(_FACTORS[-1])
    lo_t, hi_t = _TEMPS[idx - 1], _TEMPS[idx]
    lo_f, hi_f = _FACTORS[idx - 1], _FACTORS[idx]
    fraction = (temp_c - lo_t) / (hi_t - lo_t)
    return round(lo_f + fraction * (hi_f - lo_f), 3)


def adjust_uptake(uptake: Mapping[str, float], temp_c: float) -> Dict[str, float]:
    """Return ``uptake`` scaled by the temperature factor."""
    factor = get_uptake_factor(temp_c)
    return {nutrient: round(value * factor, 2) for nutrient, value in uptake.items()}
