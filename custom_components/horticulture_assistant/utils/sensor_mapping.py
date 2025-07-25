"""Helpers for resolving sensor entity mappings.

The mapping supports ``<sensor>_sensors`` keys storing a list of entity
ids as well as optional ``<sensor>_method`` keys controlling how multiple
sensors should be aggregated (``"mean"`` or ``"median"``).
"""
from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from .plant_profile_loader import load_profile


SENSOR_KEYS = [
    "moisture_sensors",
    "temperature_sensors",
    "humidity_sensors",
    "light_sensors",
    "ec_sensors",
    "co2_sensors",
]

METHOD_SUFFIX = "_method"


def load_sensor_map(hass: HomeAssistant, entry: ConfigEntry) -> dict[str, list[str]]:
    """Return mapping of sensor type to entity id list for ``entry``."""

    plant_id = entry.entry_id
    mapping: dict[str, list[str]] = {}

    profile = load_profile(plant_id=plant_id, base_dir=hass.config.path("plants"))
    sensors = (
        profile.get("sensor_entities")
        or profile.get("general", {}).get("sensor_entities")
        or {}
    )

    for key in SENSOR_KEYS:
        val = sensors.get(key) or sensors.get(key[:-1])
        if val:
            mapping[key] = val if isinstance(val, list) else [val]
        method_key = key.replace("_sensors", METHOD_SUFFIX)
        method_val = sensors.get(method_key)
        if isinstance(method_val, str):
            mapping[method_key] = method_val

    for key in SENSOR_KEYS:
        if key in entry.data:
            val = entry.data.get(key)
            if val:
                mapping[key] = val if isinstance(val, list) else [val]
        method_key = key.replace("_sensors", METHOD_SUFFIX)
        if method_key in entry.data:
            mval = entry.data.get(method_key)
            if isinstance(mval, str):
                mapping[method_key] = mval
    return mapping

