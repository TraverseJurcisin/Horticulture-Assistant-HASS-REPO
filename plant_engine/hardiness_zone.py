"""Helpers for working with USDA hardiness zone data."""
from __future__ import annotations

from typing import Iterable

from .utils import load_dataset

DATA_FILE = "hardiness_zone_temperatures.json"
_DATA = load_dataset(DATA_FILE)

__all__ = ["get_min_temperature", "suitable_zones"]


def get_min_temperature(zone: str) -> float | None:
    """Return minimum winter temperature in Celsius for ``zone``."""
    try:
        value = _DATA.get(str(zone))
        return float(value) if value is not None else None
    except (TypeError, ValueError):  # pragma: no cover - defensive
        return None


def suitable_zones(min_temp_c: float) -> list[str]:
    """Return zones with minimum temperature at least ``min_temp_c``."""
    zones: list[str] = []
    for zone, val in _DATA.items():
        try:
            temp = float(val)
        except (TypeError, ValueError):
            continue
        if temp >= min_temp_c:
            zones.append(str(zone))
    zones.sort(key=lambda z: float(_DATA[z]))
    return zones
