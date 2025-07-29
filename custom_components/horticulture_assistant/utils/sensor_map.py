"""Helpers for constructing sensor entity mappings.

This module converts config entry data into normalized lists of entity IDs so
other modules can easily reference the sensors for a plant.  It also provides
a merge helper for combining maps from multiple sources without duplicates.
"""
from __future__ import annotations

from typing import Iterable, Mapping, Dict

from .state_helpers import normalize_entities

# Default entity templates used when a config entry does not explicitly specify
# sensors. ``plant_id`` is interpolated into the template string.
DEFAULT_SENSORS = {
    "moisture_sensors": "sensor.{plant_id}_raw_moisture",
    "temperature_sensors": "sensor.{plant_id}_raw_temperature",
    "humidity_sensors": "sensor.{plant_id}_raw_humidity",
    "light_sensors": "sensor.{plant_id}_raw_light",
    "ec_sensors": "sensor.{plant_id}_raw_ec",
    "co2_sensors": "sensor.{plant_id}_raw_co2",
}

__all__ = ["build_sensor_map", "merge_sensor_maps", "DEFAULT_SENSORS"]


def build_sensor_map(
    entry_data: Mapping[str, object],
    plant_id: str,
    keys: Iterable[str] | None = None,
) -> Dict[str, list[str]]:
    """Return normalized sensor map for ``plant_id``.

    Parameters
    ----------
    entry_data:
        Mapping of configuration keys to entity IDs or lists of IDs.
    plant_id:
        Unique identifier for the plant used to format default entity templates.
    keys:
        Optional subset of keys to include. When ``None`` all ``DEFAULT_SENSORS``
        entries are processed.

    Returns
    -------
    dict
        Mapping of sensor categories to lists of entity IDs.
    """
    if keys is None:
        keys = DEFAULT_SENSORS.keys()

    result: Dict[str, list[str]] = {}
    for key in keys:
        default = DEFAULT_SENSORS.get(key)
        if not default:
            continue
        result[key] = normalize_entities(
            entry_data.get(key), default.format(plant_id=plant_id)
        )
    return result


def merge_sensor_maps(
    base: Mapping[str, Iterable[str]], update: Mapping[str, Iterable[str]]
) -> Dict[str, list[str]]:
    """Return ``base`` merged with ``update`` with duplicates removed.

    Parameters
    ----------
    base:
        Original sensor mapping.
    update:
        Mapping with updated values to merge into ``base``.

    Returns
    -------
    dict
        Combined mapping without duplicate entity IDs.
    """

    merged: Dict[str, list[str]] = {k: list(v) for k, v in base.items()}
    for key, values in update.items():
        if not values:
            continue
        if isinstance(values, str):
            values = [values]
        existing = merged.get(key, [])
        for item in values:
            if item not in existing:
                existing.append(item)
        merged[key] = existing
    return merged
