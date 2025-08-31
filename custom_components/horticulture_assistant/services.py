"""Service handlers for Horticulture Assistant.

These services expose high level operations for manipulating plant profiles
at runtime. They are intentionally lightweight wrappers around the
:class:`ProfileRegistry` to keep the integration's ``__init__`` module from
becoming monolithic.
"""

from __future__ import annotations

import logging
from typing import Final

import voluptuous as vol
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er

from .const import CONF_PROFILES, DOMAIN
from .profile_registry import ProfileRegistry

_LOGGER = logging.getLogger(__name__)

# Mapping of measurement names to expected device classes.  These roughly
# correspond to the roles supported by :mod:`update_sensors`.
MEASUREMENT_CLASSES: Final = {
    "temperature": SensorDeviceClass.TEMPERATURE,
    "humidity": SensorDeviceClass.HUMIDITY,
    "illuminance": SensorDeviceClass.ILLUMINANCE,
    "moisture": SensorDeviceClass.MOISTURE,
}


async def async_register_all(
    hass: HomeAssistant,
    entry,
    ai_coord,
    local_coord,
    profile_coord,
    registry: ProfileRegistry,
) -> None:
    """Register high level profile services."""

    async def _refresh_profile() -> None:
        if profile_coord:
            await profile_coord.async_request_refresh()

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
        await _refresh_profile()

    async def _srv_refresh_species(call) -> None:
        profile_id: str = call.data["profile_id"]
        await registry.async_refresh_species(profile_id)

    async def _srv_export_profiles(call) -> None:
        path = call.data["path"]
        p = await registry.async_export(path)
        _LOGGER.info("Exported %d profiles to %s", len(registry), p)

    async def _srv_create_profile(call) -> None:
        name: str = call.data["name"]
        await registry.async_add_profile(name)
        await _refresh_profile()

    async def _srv_duplicate_profile(call) -> None:
        src = call.data["source_profile_id"]
        new_name = call.data["new_name"]
        try:
            await registry.async_duplicate_profile(src, new_name)
        except ValueError as err:
            raise vol.Invalid(str(err)) from err
        await _refresh_profile()

    async def _srv_delete_profile(call) -> None:
        pid = call.data["profile_id"]
        try:
            await registry.async_delete_profile(pid)
        except ValueError as err:
            raise vol.Invalid(str(err)) from err
        await _refresh_profile()

    async def _srv_update_sensors(call) -> None:
        pid = call.data["profile_id"]
        sensors: dict[str, str] = {}
        for role in ("temperature", "humidity", "illuminance", "moisture"):
            if ent := call.data.get(role):
                if hass.states.get(ent) is None:
                    raise vol.Invalid(f"missing entity {ent}")
                sensors[role] = ent
        try:
            await registry.async_link_sensors(pid, sensors)
        except ValueError as err:
            raise vol.Invalid(str(err)) from err
        await _refresh_profile()

    async def _srv_export_profile(call) -> None:
        pid = call.data["profile_id"]
        path = call.data["path"]
        out = await registry.async_export_profile(pid, path)
        _LOGGER.info("Exported profile %s to %s", pid, out)

    async def _srv_import_profiles(call) -> None:
        path = call.data["path"]
        await registry.async_import_profiles(path)
        await _refresh_profile()

    async def _srv_refresh(call) -> None:
        if ai_coord:
            await ai_coord.async_request_refresh()
        if local_coord:
            await local_coord.async_request_refresh()
        if profile_coord:
            await profile_coord.async_request_refresh()

    async def _srv_recompute(call) -> None:
        profile_id: str | None = call.data.get("profile_id")
        if profile_id:
            profiles = entry.options.get(CONF_PROFILES, {})
            if profile_id not in profiles:
                raise vol.Invalid(f"unknown profile {profile_id}")
        if profile_coord:
            await profile_coord.async_request_refresh()

    async def _srv_reset_dli(call) -> None:
        profile_id: str | None = call.data.get("profile_id")
        if profile_coord:
            await profile_coord.async_reset_dli(profile_id)

    async def _srv_recommend_watering(call) -> dict[str, int]:
        """Suggest a watering duration based on profile metrics."""

        pid: str = call.data["profile_id"]
        if profile_coord is None:
            raise vol.Invalid("profile coordinator unavailable")
        metrics = profile_coord.data.get("profiles", {}).get(pid, {}).get("metrics") if profile_coord.data else None
        if metrics is None:
            raise vol.Invalid(f"unknown profile {pid}")
        moisture = metrics.get("moisture")
        dli = metrics.get("dli")
        minutes = 0
        if moisture is not None:
            if moisture < 20:
                minutes += 10
            elif moisture < 30:
                minutes += 5
        if dli is not None and dli < 8:
            minutes += 5
        return {"minutes": minutes}

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
        "create_profile",
        _srv_create_profile,
        schema=vol.Schema({vol.Required("name"): str}),
    )
    hass.services.async_register(
        DOMAIN,
        "duplicate_profile",
        _srv_duplicate_profile,
        schema=vol.Schema({vol.Required("source_profile_id"): str, vol.Required("new_name"): str}),
    )
    hass.services.async_register(
        DOMAIN,
        "delete_profile",
        _srv_delete_profile,
        schema=vol.Schema({vol.Required("profile_id"): str}),
    )
    hass.services.async_register(
        DOMAIN,
        "update_sensors",
        _srv_update_sensors,
        schema=vol.Schema(
            {
                vol.Required("profile_id"): str,
                vol.Optional("temperature"): cv.entity_id,
                vol.Optional("humidity"): cv.entity_id,
                vol.Optional("illuminance"): cv.entity_id,
                vol.Optional("moisture"): cv.entity_id,
            }
        ),
    )
    hass.services.async_register(
        DOMAIN,
        "export_profiles",
        _srv_export_profiles,
        schema=vol.Schema({vol.Required("path"): str}),
    )
    hass.services.async_register(
        DOMAIN,
        "export_profile",
        _srv_export_profile,
        schema=vol.Schema({vol.Required("profile_id"): str, vol.Required("path"): str}),
    )
    hass.services.async_register(
        DOMAIN,
        "import_profiles",
        _srv_import_profiles,
        schema=vol.Schema({vol.Required("path"): str}),
    )
    hass.services.async_register(
        DOMAIN,
        "refresh",
        _srv_refresh,
        schema=vol.Schema({}),
    )
    hass.services.async_register(
        DOMAIN,
        "recompute",
        _srv_recompute,
        schema=vol.Schema({vol.Optional("profile_id"): str}),
    )
    hass.services.async_register(
        DOMAIN,
        "reset_dli",
        _srv_reset_dli,
        schema=vol.Schema({vol.Optional("profile_id"): str}),
    )
    hass.services.async_register(
        DOMAIN,
        "recommend_watering",
        _srv_recommend_watering,
        schema=vol.Schema({vol.Required("profile_id"): str}),
        supports_response=True,
    )

    # Preserve backwards compatible top-level sensors mapping if it exists.
    # This mirrors the behaviour of earlier versions of the integration where
    # sensors were stored directly under ``entry.options['sensors']``.
    if entry.options.get("sensors") and CONF_PROFILES not in entry.options:
        _LOGGER.debug("Migrating legacy sensors mapping into profile registry")
        profile_id = entry.options.get("plant_id", "profile")
        profiles = dict(entry.options.get(CONF_PROFILES, {}))
        profiles[profile_id] = {
            "name": entry.title or profile_id,
            "sensors": dict(entry.options.get("sensors")),
        }
        new_opts = dict(entry.options)
        new_opts[CONF_PROFILES] = profiles
        hass.config_entries.async_update_entry(entry, options=new_opts)
        entry.options = new_opts
