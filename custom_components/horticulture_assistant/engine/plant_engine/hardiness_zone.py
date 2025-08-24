"""Helpers for working with USDA hardiness zone data."""

from __future__ import annotations

from collections.abc import Mapping

from .utils import load_dataset

DATA_FILE = "temperature/hardiness_zone_temperatures.json"
_DATA = load_dataset(DATA_FILE)
PLANT_FILE = "plants/plant_hardiness_zones.json"
_PLANT_ZONES: Mapping[str, Mapping[str, str]] = load_dataset(PLANT_FILE)

__all__ = [
    "get_min_temperature",
    "suitable_zones",
    "get_hardiness_range",
    "is_plant_suitable_for_zone",
    "plants_for_zone",
]


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


def get_hardiness_range(plant_type: str) -> tuple[str, str] | None:
    """Return (min_zone, max_zone) recommended for ``plant_type``."""
    info = _PLANT_ZONES.get(plant_type.lower())
    if not isinstance(info, Mapping):
        return None
    min_z = info.get("min_zone")
    max_z = info.get("max_zone")
    if isinstance(min_z, str) and isinstance(max_z, str):
        return min_z, max_z
    return None


def is_plant_suitable_for_zone(plant_type: str, zone: str) -> bool:
    """Return ``True`` if ``zone`` falls within the plant's recommended range."""
    rng = get_hardiness_range(plant_type)
    if not rng:
        return True
    min_z, max_z = rng
    try:
        zone_v = float(zone)
        return float(min_z) <= zone_v <= float(max_z)
    except (TypeError, ValueError):
        return False


def plants_for_zone(zone: str) -> list[str]:
    """Return plant types whose recommended range includes ``zone``."""
    results: list[str] = []
    try:
        zone_v = float(zone)
    except (TypeError, ValueError):
        return results
    for plant, info in _PLANT_ZONES.items():
        if not isinstance(info, Mapping):
            continue
        try:
            min_z = float(info.get("min_zone", "0"))
            max_z = float(info.get("max_zone", "0"))
        except (TypeError, ValueError):
            continue
        if min_z <= zone_v <= max_z:
            results.append(plant)
    return sorted(results)
