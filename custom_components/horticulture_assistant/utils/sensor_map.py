"""Helpers for constructing sensor entity mappings."""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from .state_helpers import normalize_entities, parse_entities

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
) -> dict[str, list[str]]:
    """Return normalized sensor map for ``plant_id`` based on ``entry_data``."""
    if keys is None:
        keys = DEFAULT_SENSORS.keys()

    result: dict[str, list[str]] = {}
    for key in keys:
        default = DEFAULT_SENSORS.get(key)
        if not default:
            continue
        result[key] = normalize_entities(entry_data.get(key), default.format(plant_id=plant_id))
    return result


def merge_sensor_maps(
    base: Mapping[str, Iterable[str] | str],
    update: Mapping[str, Iterable[str] | str],
) -> dict[str, list[str]]:
    """Return ``base`` merged with ``update`` while preserving order.

    Sensor lists from ``base`` retain their original order and any new sensors
    from ``update`` are appended, skipping duplicates. Values may be strings or
    iterables and are parsed using the same logic as ``normalize_entities``.
    """

    merged: dict[str, list[str]] = {}
    for key in set(base) | set(update):
        base_list = parse_entities(base.get(key))
        update_list = parse_entities(update.get(key))
        merged[key] = list(dict.fromkeys(base_list + update_list))
    return merged
