"""Helpers for modeling heat memory responses by crop."""

from __future__ import annotations

from functools import cache

from .utils import list_dataset_entries, load_dataset, normalize_key

DATA_FILE = "temperature/heat_memory_guidelines.json"


@cache
def _data() -> dict[str, dict[str, float]]:
    return load_dataset(DATA_FILE)


__all__ = [
    "list_supported_plants",
    "get_heat_memory_info",
    "calculate_heat_memory_index",
    "recommend_heat_recovery",
]


def list_supported_plants() -> list[str]:
    """Return plant types with heat memory data."""
    return list_dataset_entries(_data())


def get_heat_memory_info(plant_type: str) -> dict[str, float] | None:
    """Return heat memory parameters for ``plant_type`` if available."""
    return _data().get(normalize_key(plant_type))


def calculate_heat_memory_index(plant_type: str, exposure_days: int) -> float:
    """Return tolerance shift in °C from heat exposure."""
    info = get_heat_memory_info(plant_type)
    if not info:
        return 0.0
    lag = float(info.get("lag_days", 0))
    delta = float(info.get("tolerance_delta_c", 0))
    if lag <= 0:
        return 0.0
    fraction = min(1.0, exposure_days / lag)
    index = fraction * delta
    return round(index, 2)


def recommend_heat_recovery(plant_type: str) -> dict[str, float]:
    """Return nutrient adjustments to aid recovery after heat stress."""
    info = get_heat_memory_info(plant_type) or {}
    rec: dict[str, float] = {}
    ec = info.get("ec_adjustment_pct")
    if ec:
        rec["ec_adjustment_pct"] = float(ec)
    ca = info.get("foliar_ca_days")
    if ca:
        rec["foliar_ca_days"] = int(ca)
    return rec
