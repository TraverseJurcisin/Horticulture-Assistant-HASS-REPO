"""Service handlers for Horticulture Assistant.

These services expose high level operations for manipulating plant profiles
at runtime. They are intentionally lightweight wrappers around the
:class:`ProfileRegistry` to keep the integration's ``__init__`` module from
becoming monolithic.
"""

from __future__ import annotations

import contextlib
import logging
from typing import Final

import voluptuous as vol
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_PROFILES, DOMAIN
from .irrigation_bridge import async_apply_irrigation
from .profile_registry import ProfileRegistry
from .storage import LocalStore

_LOGGER = logging.getLogger(__name__)

# Names of services registered by this module. Used for clean unregistration
# when the final config entry is unloaded. The list is populated dynamically
# as services are registered to ensure it stays in sync with actual service
# exposure.
SERVICE_NAMES: list[str] = []

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
    entry: ConfigEntry,
    ai_coord: DataUpdateCoordinator | None,
    local_coord: DataUpdateCoordinator | None,
    profile_coord: DataUpdateCoordinator | None,
    registry: ProfileRegistry,
    store: LocalStore,
) -> None:
    """Register high level profile services."""

    if SERVICE_NAMES:
        return

    def _register(
        name: str,
        handler,
        *,
        schema: vol.Schema | None = None,
        supports_response: bool = False,
    ) -> None:
        hass.services.async_register(
            DOMAIN,
            name,
            handler,
            schema=schema,
            supports_response=supports_response,
        )
        SERVICE_NAMES.append(name)

    async def _refresh_profile() -> None:
        if profile_coord:
            await profile_coord.async_request_refresh()

    async def _srv_replace_sensor(call: ServiceCall) -> None:
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

    async def _srv_refresh_species(call: ServiceCall) -> None:
        profile_id: str = call.data["profile_id"]
        await registry.async_refresh_species(profile_id)

    async def _srv_export_profiles(call: ServiceCall) -> None:
        path = call.data["path"]
        p = await registry.async_export(path)
        _LOGGER.info("Exported %d profiles to %s", len(registry), p)

    async def _srv_create_profile(call: ServiceCall) -> None:
        name: str = call.data["name"]
        await registry.async_add_profile(name)
        await _refresh_profile()

    async def _srv_duplicate_profile(call: ServiceCall) -> None:
        src = call.data["source_profile_id"]
        new_name = call.data["new_name"]
        try:
            await registry.async_duplicate_profile(src, new_name)
        except ValueError as err:
            raise vol.Invalid(str(err)) from err
        await _refresh_profile()

    async def _srv_delete_profile(call: ServiceCall) -> None:
        pid = call.data["profile_id"]
        try:
            await registry.async_delete_profile(pid)
        except ValueError as err:
            raise vol.Invalid(str(err)) from err
        await _refresh_profile()

    async def _srv_update_sensors(call: ServiceCall) -> None:
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

    async def _srv_export_profile(call: ServiceCall) -> None:
        pid = call.data["profile_id"]
        path = call.data["path"]
        out = await registry.async_export_profile(pid, path)
        _LOGGER.info("Exported profile %s to %s", pid, out)

    async def _srv_import_profiles(call: ServiceCall) -> None:
        path = call.data["path"]
        await registry.async_import_profiles(path)
        await _refresh_profile()

    async def _srv_import_template(call: ServiceCall) -> None:
        template = call.data["template"]
        name = call.data.get("name")
        try:
            await registry.async_import_template(template, name)
        except ValueError as err:
            raise vol.Invalid(str(err)) from err
        await _refresh_profile()

    async def _srv_refresh(call: ServiceCall) -> None:
        if ai_coord:
            await ai_coord.async_request_refresh()
        if local_coord:
            await local_coord.async_request_refresh()
        if profile_coord:
            await profile_coord.async_request_refresh()

    async def _srv_recompute(call: ServiceCall) -> None:
        profile_id: str | None = call.data.get("profile_id")
        if profile_id:
            profiles = entry.options.get(CONF_PROFILES, {})
            if profile_id not in profiles:
                raise vol.Invalid(f"unknown profile {profile_id}")
        if profile_coord:
            await profile_coord.async_request_refresh()

    async def _srv_reset_dli(call: ServiceCall) -> None:
        profile_id: str | None = call.data.get("profile_id")
        if profile_coord:
            await profile_coord.async_reset_dli(profile_id)

    async def _srv_list_profiles(call: ServiceCall) -> ServiceResponse:
        """Return identifiers and names of all known profiles."""

        return {"profiles": {p.plant_id: p.display_name for p in registry.list_profiles()}}

    async def _srv_recommend_watering(call: ServiceCall) -> ServiceResponse:
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

    async def _srv_recalculate_targets(call: ServiceCall) -> None:
        plant_id = call.data["plant_id"]
        assert store.data is not None
        plants = store.data.setdefault("plants", {})
        if plant_id not in plants:
            raise vol.Invalid(f"unknown plant {plant_id}")
        if local_coord:
            await local_coord.async_request_refresh()

    async def _srv_run_recommendation(call: ServiceCall) -> None:
        plant_id = call.data["plant_id"]
        assert store.data is not None
        plants = store.data.setdefault("plants", {})
        if plant_id not in plants:
            raise vol.Invalid(f"unknown plant {plant_id}")
        prev = ai_coord.data.get("recommendation") if ai_coord else None
        if ai_coord:
            with contextlib.suppress(UpdateFailed):
                await ai_coord.async_request_refresh()
        if call.data.get("approve") and ai_coord:
            plants.setdefault(plant_id, {})["recommendation"] = ai_coord.data.get("recommendation", prev)
            await store.save()

    async def _srv_apply_irrigation(call: ServiceCall) -> None:
        profile_id = call.data["profile_id"]
        provider = call.data.get("provider", "auto")
        zone = call.data.get("zone")
        reg = er.async_get(hass)
        unique_id = f"{DOMAIN}_{entry.entry_id}_{profile_id}_irrigation_rec"
        rec_entity = reg.async_get_entity_id("sensor", DOMAIN, unique_id)
        seconds: float | None = None
        if rec_entity:
            state = hass.states.get(rec_entity)
            try:
                seconds = float(state.state)
            except (TypeError, ValueError):
                seconds = None
        if seconds is None:
            raise vol.Invalid("no recommendation available")
        if provider == "auto":
            if hass.services.has_service("irrigation_unlimited", "run_zone"):
                provider = "irrigation_unlimited"
            elif hass.services.has_service("opensprinkler", "run_once"):
                provider = "opensprinkler"
            else:
                raise vol.Invalid("no irrigation provider")
        await async_apply_irrigation(hass, provider, zone, seconds)

    async def _srv_resolve_profile(call: ServiceCall) -> None:
        pid = call.data["profile_id"]
        from .profile.store import async_save_profile_from_options
        from .resolver import PreferenceResolver

        await PreferenceResolver(hass).resolve_profile(entry, pid)
        await async_save_profile_from_options(hass, entry, pid)

    async def _srv_resolve_all(call: ServiceCall) -> None:
        from .profile.store import async_save_profile_from_options
        from .resolver import PreferenceResolver

        resolver = PreferenceResolver(hass)
        for pid in entry.options.get(CONF_PROFILES, {}):
            await resolver.resolve_profile(entry, pid)
            await async_save_profile_from_options(hass, entry, pid)

    async def _srv_generate_profile(call: ServiceCall) -> None:
        pid = call.data["profile_id"]
        mode = call.data["mode"]
        source_profile_id = call.data.get("source_profile_id")
        from .resolver import generate_profile

        await generate_profile(hass, entry, pid, mode, source_profile_id)

    async def _srv_clear_caches(call: ServiceCall) -> None:
        from .ai_client import clear_ai_cache
        from .opb_client import clear_opb_cache

        clear_ai_cache()
        clear_opb_cache()

    _register(
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
    _register(
        "refresh_species",
        _srv_refresh_species,
        schema=vol.Schema({vol.Required("profile_id"): str}),
    )
    _register(
        "create_profile",
        _srv_create_profile,
        schema=vol.Schema({vol.Required("name"): str}),
    )
    _register(
        "duplicate_profile",
        _srv_duplicate_profile,
        schema=vol.Schema({vol.Required("source_profile_id"): str, vol.Required("new_name"): str}),
    )
    _register(
        "delete_profile",
        _srv_delete_profile,
        schema=vol.Schema({vol.Required("profile_id"): str}),
    )
    _register(
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
    _register(
        "export_profiles",
        _srv_export_profiles,
        schema=vol.Schema({vol.Required("path"): str}),
    )
    _register(
        "export_profile",
        _srv_export_profile,
        schema=vol.Schema({vol.Required("profile_id"): str, vol.Required("path"): str}),
    )
    _register(
        "import_profiles",
        _srv_import_profiles,
        schema=vol.Schema({vol.Required("path"): str}),
    )
    _register(
        "import_template",
        _srv_import_template,
        schema=vol.Schema({vol.Required("template"): str, vol.Optional("name"): str}),
    )
    _register(
        "refresh",
        _srv_refresh,
        schema=vol.Schema({}),
    )
    _register(
        "recompute",
        _srv_recompute,
        schema=vol.Schema({vol.Optional("profile_id"): str}),
    )
    _register(
        "reset_dli",
        _srv_reset_dli,
        schema=vol.Schema({vol.Optional("profile_id"): str}),
    )
    _register(
        "list_profiles",
        _srv_list_profiles,
        schema=vol.Schema({}),
        supports_response=True,
    )
    _register(
        "recommend_watering",
        _srv_recommend_watering,
        schema=vol.Schema({vol.Required("profile_id"): str}),
        supports_response=True,
    )

    _register(
        "recalculate_targets",
        _srv_recalculate_targets,
        schema=vol.Schema({vol.Required("plant_id"): str}),
    )
    _register(
        "run_recommendation",
        _srv_run_recommendation,
        schema=vol.Schema(
            {
                vol.Required("plant_id"): str,
                vol.Optional("approve", default=False): bool,
            }
        ),
    )
    _register(
        "apply_irrigation_plan",
        _srv_apply_irrigation,
        schema=vol.Schema(
            {
                vol.Required("profile_id"): str,
                vol.Optional("provider", default="auto"): vol.In(
                    [
                        "auto",
                        "irrigation_unlimited",
                        "opensprinkler",
                    ]
                ),
                vol.Optional("zone"): str,
            }
        ),
    )
    _register(
        "resolve_profile",
        _srv_resolve_profile,
        schema=vol.Schema({vol.Required("profile_id"): str}),
    )
    _register("resolve_all", _srv_resolve_all)
    _register(
        "generate_profile",
        _srv_generate_profile,
        schema=vol.Schema(
            {
                vol.Required("profile_id"): str,
                vol.Required("mode"): vol.In(["clone", "opb", "ai"]),
                vol.Optional("source_profile_id"): str,
            }
        ),
    )
    _register("clear_caches", _srv_clear_caches)

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


async def async_unregister_all(hass: HomeAssistant) -> None:
    """Unregister all services exposed by the integration."""

    for name in SERVICE_NAMES:
        with contextlib.suppress(Exception):
            hass.services.async_remove(DOMAIN, name)
    SERVICE_NAMES.clear()
