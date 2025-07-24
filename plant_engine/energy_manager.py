"""Energy usage estimation utilities for HVAC systems and lighting."""
from __future__ import annotations

from functools import lru_cache
from typing import Dict

from .utils import load_dataset, normalize_key

HVAC_FILE = "hvac_energy_coefficients.json"
RATE_FILE = "electricity_rates.json"
MONTHLY_RATE_FILE = "electricity_rates_monthly.json"

# Cache datasets via load_dataset
_HVAC_DATA: Dict[str, Dict[str, float]] = load_dataset(HVAC_FILE)
_RATES: Dict[str, float] = load_dataset(RATE_FILE)
_MONTHLY_RATES: Dict[str, Dict[str, float]] = load_dataset(MONTHLY_RATE_FILE)

__all__ = [
    "get_energy_coefficient",
    "estimate_hvac_energy",
    "get_electricity_rate",
    "estimate_lighting_energy",
    "estimate_lighting_cost",
    "get_monthly_electricity_rate",
    "estimate_lighting_cost_monthly",
]


@lru_cache(maxsize=None)
def get_energy_coefficient(system: str) -> float:
    """Return kWh per degree-day coefficient for an HVAC ``system``."""
    entry = _HVAC_DATA.get(normalize_key(system), {})
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


@lru_cache(maxsize=None)
def get_electricity_rate(region: str | None = None) -> float:
    """Return cost per kWh for ``region`` or the default rate."""

    key = normalize_key(region) if region else "default"
    rate = _RATES.get(key)
    if rate is None:
        rate = _RATES.get("default", 0.0)
    try:
        return float(rate)
    except (TypeError, ValueError):
        return 0.0


def estimate_lighting_energy(power_watts: float, hours: float) -> float:
    """Return kWh for running ``power_watts`` lights for ``hours``."""

    if power_watts <= 0 or hours <= 0:
        raise ValueError("power_watts and hours must be positive")
    kwh = power_watts * hours / 1000
    return round(kwh, 2)


def estimate_lighting_cost(
    power_watts: float, hours: float, region: str | None = None
) -> float:
    """Return lighting energy cost for ``power_watts`` and ``hours``."""

    kwh = estimate_lighting_energy(power_watts, hours)
    rate = get_electricity_rate(region)
    return round(kwh * rate, 2)


@lru_cache(maxsize=None)
def get_monthly_electricity_rate(region: str | None, month: int) -> float:
    """Return electricity rate for ``region`` and ``month`` (1-12)."""

    if not 1 <= month <= 12:
        raise ValueError("month must be between 1 and 12")

    key = normalize_key(region) if region else "default"
    rates = _MONTHLY_RATES.get(key) or _MONTHLY_RATES.get("default", {})
    rate = rates.get(str(month))
    if rate is None:
        rate = _RATES.get(key, _RATES.get("default", 0.0))
    try:
        return float(rate)
    except (TypeError, ValueError):
        return 0.0


def estimate_lighting_cost_monthly(
    power_watts: float, hours: float, month: int, region: str | None = None
) -> float:
    """Return lighting cost using month-specific electricity rates."""

    kwh = estimate_lighting_energy(power_watts, hours)
    rate = get_monthly_electricity_rate(region, month)
    return round(kwh * rate, 2)

