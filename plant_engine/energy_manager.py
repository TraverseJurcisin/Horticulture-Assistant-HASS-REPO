"""Energy usage estimation utilities for HVAC systems."""
from __future__ import annotations

from functools import lru_cache
from typing import Dict

from .utils import load_dataset, normalize_key

DATA_FILE = "hvac_energy_coefficients.json"

# Cache dataset via load_dataset
_DATA: Dict[str, Dict[str, float]] = load_dataset(DATA_FILE)

__all__ = [
    "get_energy_coefficient",
    "estimate_hvac_energy",
]


@lru_cache(maxsize=None)
def get_energy_coefficient(system: str) -> float:
    """Return kWh per degree-day coefficient for an HVAC ``system``."""
    entry = _DATA.get(normalize_key(system), {})
    try:
        return float(entry.get("kwh_per_degree_day", 0))
    except (TypeError, ValueError):
        return 0.0


def estimate_hvac_energy(
    current_temp_c: float,
    target_temp_c: float,
    hours: float,
    system: str,
) -> float:
    """Return estimated kWh to maintain ``target_temp_c`` for ``hours``."""
    if hours <= 0:
        raise ValueError("hours must be positive")
    coeff = get_energy_coefficient(system)
    if coeff <= 0:
        return 0.0
    degree_hours = abs(target_temp_c - current_temp_c) * hours
    kwh = degree_hours * (coeff / 24)
    return round(kwh, 2)
