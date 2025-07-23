"""Energy cost estimation utilities."""
from __future__ import annotations

from functools import lru_cache
from typing import Mapping

from .utils import load_dataset

RATE_FILE = "energy_rates.json"

__all__ = [
    "get_energy_rate",
    "estimate_lighting_energy",
    "estimate_lighting_cost",
    "estimate_heating_energy",
    "estimate_heating_cost",
]

@lru_cache(maxsize=None)
def get_energy_rate() -> float:
    """Return electricity cost in USD per kWh from :data:`energy_rates.json`."""
    data = load_dataset(RATE_FILE)
    try:
        return float(data.get("electricity_usd_per_kwh", 0.12))
    except (TypeError, ValueError):
        return 0.12


def estimate_lighting_energy(photoperiod_hours: float, power_w: float) -> float:
    """Return kWh consumed by lighting given hours and fixture wattage."""
    if photoperiod_hours < 0 or power_w < 0:
        raise ValueError("photoperiod_hours and power_w must be non-negative")
    return round(power_w * photoperiod_hours / 1000, 3)


def estimate_lighting_cost(
    photoperiod_hours: float, power_w: float, *, rate: float | None = None
) -> float:
    """Return estimated lighting cost in USD."""
    if rate is None:
        rate = get_energy_rate()
    energy = estimate_lighting_energy(photoperiod_hours, power_w)
    return round(energy * rate, 2)


def estimate_heating_energy(
    target_temp_c: float,
    outside_temp_c: float,
    volume_m3: float,
    *,
    insulation_factor: float = 1.0,
) -> float:
    """Return approximate kWh required to maintain indoor temperature."""
    if insulation_factor <= 0 or volume_m3 <= 0:
        raise ValueError("volume_m3 and insulation_factor must be positive")
    delta = max(0.0, target_temp_c - outside_temp_c)
    base_kwh_per_m3_c = 0.05
    energy = delta * volume_m3 * base_kwh_per_m3_c / insulation_factor
    return round(energy, 3)


def estimate_heating_cost(
    target_temp_c: float,
    outside_temp_c: float,
    volume_m3: float,
    *,
    insulation_factor: float = 1.0,
    rate: float | None = None,
) -> float:
    """Return estimated heating cost in USD."""
    if rate is None:
        rate = get_energy_rate()
    energy = estimate_heating_energy(
        target_temp_c,
        outside_temp_c,
        volume_m3,
        insulation_factor=insulation_factor,
    )
    return round(energy * rate, 2)
