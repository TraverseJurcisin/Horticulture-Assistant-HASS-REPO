from __future__ import annotations

"""Service handlers for Horticulture Assistant.

These services expose high level operations for manipulating plant profiles
at runtime.  They are intentionally lightweight wrappers around the
:class:`ProfileRegistry` to keep the integration's ``__init__`` module from
becoming monolithic.
"""

import logging
from typing import Final

import voluptuous as vol

from .const import CONF_PROFILES, DOMAIN  # noqa: E402
from .profile_registry import ProfileRegistry  # noqa: E402

try:  # pragma: no cover - allow import without Home Assistant installed
    from homeassistant.components.sensor import SensorDeviceClass
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import config_validation as cv
    from homeassistant.helpers import entity_registry as er
except (ModuleNotFoundError, ImportError):  # pragma: no cover
    import types
    from enum import Enum

    class SensorDeviceClass(str, Enum):  # type: ignore[misc]
        HUMIDITY = "humidity"
        TEMPERATURE = "temperature"
        ILLUMINANCE = "illuminance"
        MOISTURE = "moisture"

    class _ConfigValidationFallback:  # pylint: disable=too-few-public-methods
        entity_id = str

    cv = _ConfigValidationFallback()  # type: ignore[assignment]

    class _DummyEntry:
        def __init__(self, dc=None):
            self.device_class = dc
            self.original_device_class = dc

    class _DummyRegistry:
        def __init__(self):
            self._entries = {}

        def async_get_or_create(
            self, _domain, _platform, _unique_id, suggested_object_id=None, original_device_class=None
        ):
            eid = suggested_object_id or _unique_id
            self._entries[eid] = _DummyEntry(original_device_class)
            return self._entries[eid]

        def async_get(self, entity_id):
            return self._entries.get(entity_id)

    _dummy_registry = _DummyRegistry()

    def async_get(_hass):  # pylint: disable=unused-argument
        return _dummy_registry

    er = types.SimpleNamespace(async_get=async_get)

    class HomeAssistant:  # type: ignore[empty-body]
        pass

_LOGGER = logging.getLogger(__name__)

# Mapping of measurement names to expected device classes.  These roughly
# correspond to the roles supported by :mod:`link_sensors`.
MEASUREMENT_CLASSES: Final = {
    "temperature": SensorDeviceClass.TEMPERATURE,
    "humidity": SensorDeviceClass.HUMIDITY,
    "illuminance": SensorDeviceClass.ILLUMINANCE,
    "moisture": SensorDeviceClass.MOISTURE,
}


async def async_setup_services(
    hass: HomeAssistant, entry, registry: ProfileRegistry
) -> None:
    """Register high level profile services."""

    async def _srv_replace_sensor(call) -> None:
        profile_id: str = call.data["profile_id"]
        measurement: str = call.data["measurement"]
        entity_id: str = call.data["entity_id"]

        if measurement not in MEASUREMENT_CLASSES:
            raise vol.Invalid(f"unknown measurement {measurement}")
        if hass.states.get(entity_id) is None:
            raise vol.Invalid(f"missing entity {entity_id}")

        reg = er.async_get(hass)
        reg_entry = reg.async_get(entity_id)
        expected = MEASUREMENT_CLASSES[measurement]
        actual = None
        if reg_entry:
            actual = reg_entry.device_class or reg_entry.original_device_class
        if expected and (reg_entry is None or actual != expected.value):
            raise vol.Invalid("device class mismatch")

        await registry.async_replace_sensor(profile_id, measurement, entity_id)

    async def _srv_refresh_species(call) -> None:
        profile_id: str = call.data["profile_id"]
        await registry.async_refresh_species(profile_id)

    async def _srv_export_profiles(call) -> None:
        path = call.data["path"]
        p = await registry.async_export(path)
        _LOGGER.info("Exported %d profiles to %s", len(registry), p)

    hass.services.async_register(
        DOMAIN,
        "replace_sensor",
        _srv_replace_sensor,
        schema=vol.Schema(
            {
                vol.Required("profile_id"): str,
                vol.Required("measurement"): vol.In(sorted(MEASUREMENT_CLASSES)),
                vol.Required("entity_id"): cv.entity_id,
            }
        ),
    )
    hass.services.async_register(
        DOMAIN,
        "refresh_species",
        _srv_refresh_species,
        schema=vol.Schema({vol.Required("profile_id"): str}),
    )
    hass.services.async_register(
        DOMAIN,
        "export_profiles",
        _srv_export_profiles,
        schema=vol.Schema({vol.Required("path"): str}),
    )

    # Preserve backwards compatible top-level sensors mapping if it exists.
    # This mirrors the behaviour of earlier versions of the integration where
    # sensors were stored directly under ``entry.options['sensors']``.
    if entry.options.get("sensors") and CONF_PROFILES not in entry.options:
        _LOGGER.debug("Migrating legacy sensors mapping into profile registry")
        profile_id = entry.options.get("plant_id", "profile")
        registry.entry.options.setdefault(CONF_PROFILES, {})[profile_id] = {
            "name": entry.title or profile_id,
            "sensors": dict(entry.options.get("sensors")),
        }
