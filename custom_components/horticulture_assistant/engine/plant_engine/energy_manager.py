"""Energy usage estimation utilities for HVAC systems and lighting."""
from __future__ import annotations

from functools import lru_cache
from typing import Dict, Iterable

from .utils import load_dataset, normalize_key

HVAC_FILE = "energy/hvac_energy_coefficients.json"
RATE_FILE = "energy/electricity_rates.json"
LIGHT_EFF_FILE = "light/light_efficiency.json"
EMISSION_FILE = "energy/energy_emission_factors.json"

# Cache datasets via load_dataset
_HVAC_DATA: Dict[str, Dict[str, float]] = load_dataset(HVAC_FILE)
_RATES: Dict[str, float] = load_dataset(RATE_FILE)
_LIGHT_EFF: Dict[str, Dict[str, float]] = load_dataset(LIGHT_EFF_FILE)
_EMISSION_FACTORS: Dict[str, float] = load_dataset(EMISSION_FILE)

__all__ = [
    "get_energy_coefficient",
    "estimate_hvac_energy",
    "estimate_hvac_cost",
    "get_electricity_rate",
    "estimate_lighting_energy",
    "estimate_lighting_cost",
    "get_light_efficiency",
    "estimate_dli_from_power",
    "estimate_hvac_energy_series",
    "estimate_hvac_cost_series",
    "get_emission_factor",
    "estimate_lighting_emissions",
    "estimate_hvac_emissions",
    "estimate_hvac_emissions_series",
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
def get_emission_factor(source: str | None = None) -> float:
    """Return kg CO₂ per kWh emission factor for an energy ``source``."""

    key = normalize_key(source) if source else "default"
    factor = _EMISSION_FACTORS.get(key)
    if factor is None:
        factor = _EMISSION_FACTORS.get("default", 0.0)
    try:
        return float(factor)
    except (TypeError, ValueError):
        return 0.0


def estimate_lighting_emissions(
    power_watts: float, hours: float, source: str | None = None
) -> float:
    """Return kg CO₂ emitted by lighting energy use."""

    energy = estimate_lighting_energy(power_watts, hours)
    factor = get_emission_factor(source)
    return round(energy * factor, 3)


def estimate_hvac_cost(
    current_temp_c: float,
    target_temp_c: float,
    hours: float,
    system: str,
    region: str | None = None,
) -> float:
    """Return cost to maintain ``target_temp_c`` for ``hours`` using ``system``."""

    energy = estimate_hvac_energy(current_temp_c, target_temp_c, hours, system)
    rate = get_electricity_rate(region)
    return round(energy * rate, 2)


def estimate_hvac_emissions(
    current_temp_c: float,
    target_temp_c: float,
    hours: float,
    system: str,
    source: str | None = None,
) -> float:
    """Return kg CO₂ emitted maintaining ``target_temp_c`` for ``hours``."""

    energy = estimate_hvac_energy(current_temp_c, target_temp_c, hours, system)
    factor = get_emission_factor(source)
    return round(energy * factor, 3)


@lru_cache(maxsize=None)
def get_light_efficiency(fixture: str) -> float:
    """Return µmol per joule efficiency for a lighting ``fixture``."""

    entry = _LIGHT_EFF.get(normalize_key(fixture), _LIGHT_EFF.get("default", {}))
    try:
        return float(entry.get("umol_per_j", 0.0))
    except (TypeError, ValueError):
        return 0.0


def estimate_dli_from_power(
    power_watts: float,
    hours: float,
    fixture: str,
    area_m2: float = 1.0,
) -> float:
    """Return estimated DLI for ``fixture`` running at ``power_watts``."""

    if power_watts <= 0 or hours <= 0 or area_m2 <= 0:
        raise ValueError("power_watts, hours and area_m2 must be positive")
    eff = get_light_efficiency(fixture)
    umol = power_watts * hours * 3600 * eff
    mol = umol / 1_000_000
    return round(mol / area_m2, 2)


def estimate_hvac_energy_series(
    start_temp_c: float,
    target_temps: Iterable[float],
    hours_per_step: float,
    system: str,
) -> list[float]:
    """Return kWh estimates for sequential temperature setpoints.

    Each step represents ``hours_per_step`` hours at the corresponding
    target temperature starting from ``start_temp_c``. The current
    temperature is updated after each step so the energy reflects the
    difference between consecutive setpoints.
    """

    if hours_per_step <= 0:
        raise ValueError("hours_per_step must be positive")

    coeff = get_energy_coefficient(system)
    if coeff <= 0:
        return [0.0 for _ in target_temps]

    temps = [float(t) for t in target_temps]
    energy: list[float] = []
    prev = float(start_temp_c)
    for temp in temps:
        degree_hours = abs(temp - prev) * hours_per_step
        kwh = degree_hours * (coeff / 24)
        energy.append(round(kwh, 2))
        prev = temp

    return energy


def estimate_hvac_cost_series(
    start_temp_c: float,
    target_temps: Iterable[float],
    hours_per_step: float,
    system: str,
    region: str | None = None,
) -> list[float]:
    """Return cost estimates for sequential HVAC setpoints."""

    energies = estimate_hvac_energy_series(
        start_temp_c, target_temps, hours_per_step, system
    )
    rate = get_electricity_rate(region)
    return [round(e * rate, 2) for e in energies]


def estimate_hvac_emissions_series(
    start_temp_c: float,
    target_temps: Iterable[float],
    hours_per_step: float,
    system: str,
    source: str | None = None,
) -> list[float]:
    """Return emission estimates for sequential HVAC setpoints."""

    energies = estimate_hvac_energy_series(
        start_temp_c, target_temps, hours_per_step, system
    )
    factor = get_emission_factor(source)
    return [round(e * factor, 3) for e in energies]
