from __future__ import annotations

import logging
from datetime import timedelta

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from aiohttp import ClientError
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.update_coordinator import UpdateFailed

from . import services as ha_services
from .api import ChatApi
from .calibration import services as calibration_services
from .const import (
    CONF_API_KEY,
    CONF_BASE_URL,
    CONF_CO2_SENSOR,
    CONF_EC_SENSOR,
    CONF_KEEP_STALE,
    CONF_MODEL,
    CONF_MOISTURE_SENSOR,
    CONF_PROFILES,
    CONF_TEMPERATURE_SENSOR,
    CONF_UPDATE_INTERVAL,
    DEFAULT_BASE_URL,
    DEFAULT_KEEP_STALE,
    DEFAULT_MODEL,
    DEFAULT_UPDATE_MINUTES,
    DOMAIN,
    PLATFORMS,
)
from .coordinator import HorticultureCoordinator
from .coordinator_ai import HortiAICoordinator
from .coordinator_local import HortiLocalCoordinator
from .entity_utils import ensure_entities_exist
from .irrigation_bridge import async_apply_irrigation
from .opb_client import OpenPlantbookClient
from .profile_registry import ProfileRegistry
from .storage import LocalStore
from .utils.entry_helpers import store_entry_data
from .utils.paths import ensure_local_data_paths

SENSORS_SCHEMA = vol.Schema({str: [cv.entity_id]}, extra=vol.PREVENT_EXTRA)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, _config) -> bool:
    await calibration_services.async_setup(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})
    api = ChatApi(
        hass,
        entry.data.get(CONF_API_KEY, ""),
        entry.data.get(CONF_BASE_URL, DEFAULT_BASE_URL),
        entry.data.get(CONF_MODEL, DEFAULT_MODEL),
        timeout=15.0,
    )
    store = LocalStore(hass)
    await ensure_local_data_paths(hass)
    stored = await store.load()
    minutes = max(
        1,
        int(
            entry.options.get(
                CONF_UPDATE_INTERVAL,
                entry.data.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_MINUTES),
            )
        ),
    )
    keep_stale = entry.options.get(CONF_KEEP_STALE, DEFAULT_KEEP_STALE)
    ai_coord = HortiAICoordinator(
        hass, api, store, update_minutes=minutes, initial=stored.get("recommendation")
    )
    local_coord = HortiLocalCoordinator(hass, store, update_minutes=1)
    profile_coord = HorticultureCoordinator(hass, entry.entry_id, entry.options)
    try:
        await ai_coord.async_config_entry_first_refresh()
        await local_coord.async_config_entry_first_refresh()
        await profile_coord.async_config_entry_first_refresh()
    except (TimeoutError, UpdateFailed, ClientError) as err:
        _LOGGER.warning("Initial data refresh failed: %s", err)
    except Exception as err:  # pragma: no cover - unexpected
        _LOGGER.exception("Initial data refresh failed: %s", err)
    registry = ProfileRegistry(hass, entry)
    await registry.async_load()
    hass.data[DOMAIN]["profile_registry"] = registry
    await ha_services.async_register_all(
        hass=hass,
        entry=entry,
        ai_coord=ai_coord,
        local_coord=local_coord,
        profile_coord=profile_coord,
        registry=registry,
    )
    entry_data = store_entry_data(hass, entry)
    entry_data.update(
        {
            "api": api,
            "coordinator_ai": ai_coord,
            "coordinator_local": local_coord,
            "coordinator": profile_coord,
            "store": store,
            "keep_stale": keep_stale,
        }
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _LOGGER.info("Horticulture Assistant setup complete")

    # Validate configured sensors exist
    for key in (
        CONF_MOISTURE_SENSOR,
        CONF_TEMPERATURE_SENSOR,
        CONF_EC_SENSOR,
        CONF_CO2_SENSOR,
    ):
        entity_id = entry.options.get(key)
        if entity_id:
            ensure_entities_exist(
                hass,
                f"{entry.entry_id}_{entity_id}",
                [entity_id],
                translation_key="missing_entity_option",
                placeholders={"entity_id": entity_id},
            )

    if entry.options.get("opb_enable_upload"):

        async def _opb_upload(_now):
            opb = entry.options.get("opb_credentials")
            pid = entry.options.get("species_pid")
            sensors_map: dict[str, str] = entry.options.get("sensors", {})
            if not opb or not pid or not sensors_map:
                return
            client = OpenPlantbookClient(hass, opb.get("client_id", ""), opb.get("secret", ""))
            values: dict[str, float] = {}
            for role, entity_id in sensors_map.items():
                state = hass.states.get(entity_id)
                if state is None:
                    continue
                try:
                    values[role] = float(state.state)
                except (ValueError, TypeError):
                    continue
            if not values:
                return
            loc = entry.options.get("opb_location_share", "off")
            kwargs: dict[str, float | str] = {}
            if loc == "country":
                if hass.config.country:
                    kwargs["location_country"] = hass.config.country
            elif loc == "coordinates":
                if hass.config.country:
                    kwargs["location_country"] = hass.config.country
                if hass.config.longitude is not None and hass.config.latitude is not None:
                    kwargs["location_lon"] = float(hass.config.longitude)
                    kwargs["location_lat"] = float(hass.config.latitude)
            await client.upload(entry.entry_id, pid, values, **kwargs)

        entry_data["opb_unsub"] = async_track_time_interval(hass, _opb_upload, timedelta(days=1))

    async def _handle_update_sensors(call):
        plant_id = call.data["plant_id"]
        sensors = call.data["sensors"]
        all_entities = [eid for v in sensors.values() for eid in v]
        missing = [eid for eid in all_entities if hass.states.get(eid) is None]
        ensure_entities_exist(hass, plant_id, all_entities)
        if missing:
            _LOGGER.warning("update_sensors missing entity %s", missing[0])
            raise vol.Invalid(f"missing entity {missing[0]}")
        store.data.setdefault("plants", {})
        store.data["plants"].setdefault(plant_id, {})["sensors"] = sensors
        await store.save()

    async def _handle_recalculate(call):
        plant_id = call.data["plant_id"]
        plants = store.data.setdefault("plants", {})
        if plant_id not in plants:
            raise vol.Invalid(f"unknown plant {plant_id}")
        await local_coord.async_request_refresh()

    async def _handle_run_reco(call):
        plant_id = call.data["plant_id"]
        plants = store.data.setdefault("plants", {})
        if plant_id not in plants:
            raise vol.Invalid(f"unknown plant {plant_id}")
        prev = ai_coord.data.get("recommendation")
        try:
            await ai_coord.async_request_refresh()
        except UpdateFailed:
            pass
        if call.data.get("approve"):
            plants.setdefault(plant_id, {})["recommendation"] = ai_coord.data.get(
                "recommendation", prev
            )
            await store.save()

    svc_base = DOMAIN
    hass.services.async_register(
        svc_base,
        "update_sensors",
        _handle_update_sensors,
        schema=vol.Schema({vol.Required("plant_id"): str, vol.Required("sensors"): SENSORS_SCHEMA}),
    )

    hass.services.async_register(
        svc_base,
        "recalculate_targets",
        _handle_recalculate,
        schema=vol.Schema({vol.Required("plant_id"): str}),
    )
    hass.services.async_register(
        svc_base,
        "run_recommendation",
        _handle_run_reco,
        schema=vol.Schema(
            {
                vol.Required("plant_id"): str,
                vol.Optional("approve", default=False): bool,
            }
        ),
    )

    async def _handle_apply_irrigation(call):
        profile_id = call.data["profile_id"]
        provider = call.data.get("provider", "auto")
        zone = call.data.get("zone")
        # fetch recommendation sensor
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

    hass.services.async_register(
        svc_base,
        "apply_irrigation_plan",
        _handle_apply_irrigation,
        schema=vol.Schema(
            {
                vol.Required("profile_id"): str,
                vol.Optional("provider", default="auto"): vol.In(
                    ["auto", "irrigation_unlimited", "opensprinkler"]
                ),
                vol.Optional("zone"): str,
            }
        ),
    )

    async def _svc_resolve_profile(call):
        pid = call.data["profile_id"]
        from .profile.store import async_save_profile_from_options
        from .resolver import PreferenceResolver

        await PreferenceResolver(hass).resolve_profile(entry, pid)
        await async_save_profile_from_options(hass, entry, pid)

    async def _svc_resolve_all(call):
        from .profile.store import async_save_profile_from_options
        from .resolver import PreferenceResolver

        r = PreferenceResolver(hass)
        for pid in entry.options.get(CONF_PROFILES, {}).keys():
            await r.resolve_profile(entry, pid)
            await async_save_profile_from_options(hass, entry, pid)

    async def _svc_generate_profile(call):
        pid = call.data["profile_id"]
        mode = call.data["mode"]
        source_profile_id = call.data.get("source_profile_id")
        from .resolver import generate_profile

        await generate_profile(hass, entry, pid, mode, source_profile_id)

    hass.services.async_register(
        svc_base,
        "resolve_profile",
        _svc_resolve_profile,
        schema=vol.Schema({vol.Required("profile_id"): str}),
    )
    hass.services.async_register(svc_base, "resolve_all", _svc_resolve_all)
    hass.services.async_register(
        svc_base,
        "generate_profile",
        _svc_generate_profile,
        schema=vol.Schema(
            {
                vol.Required("profile_id"): str,
                vol.Required("mode"): vol.In(["clone", "opb", "ai"]),
                vol.Optional("source_profile_id"): str,
            }
        ),
    )

    async def _svc_clear_caches(call):
        from .ai_client import clear_ai_cache
        from .opb_client import clear_opb_cache

        clear_ai_cache()
        clear_opb_cache()

    hass.services.async_register(svc_base, "clear_caches", _svc_clear_caches)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    data = hass.data.get(DOMAIN, {}).pop(entry.entry_id, {})
    unsub = data.get("opb_unsub")
    if unsub:
        try:
            unsub()
        except Exception:  # pragma: no cover - best effort cleanup
            pass
    for key in ("coordinator_ai", "coordinator_local", "coordinator"):
        coord = data.get(key)
        if coord and hasattr(coord, "async_shutdown"):
            try:
                await coord.async_shutdown()
            except Exception:  # pragma: no cover - best effort cleanup
                pass
    return unload_ok


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate old config entries to new version."""
    version = entry.version or 1
    data = {**entry.data}
    options = {**entry.options}

    if version < 2:
        options.setdefault(
            CONF_UPDATE_INTERVAL,
            data.pop(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_MINUTES),
        )
        options.setdefault(
            CONF_KEEP_STALE,
            data.pop(CONF_KEEP_STALE, DEFAULT_KEEP_STALE),
        )
        hass.config_entries.async_update_entry(entry, data=data, options=options, version=2)
    return True
