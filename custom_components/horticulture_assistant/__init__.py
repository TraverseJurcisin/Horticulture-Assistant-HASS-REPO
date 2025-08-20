from __future__ import annotations
import logging
import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from .const import (
    DOMAIN,
    PLATFORMS,
    CONF_API_KEY,
    CONF_MODEL,
    CONF_BASE_URL,
    CONF_UPDATE_INTERVAL,
    CONF_KEEP_STALE,
    CONF_MOISTURE_SENSOR,
    CONF_TEMPERATURE_SENSOR,
    CONF_EC_SENSOR,
    CONF_CO2_SENSOR,
    DEFAULT_BASE_URL,
    DEFAULT_MODEL,
    DEFAULT_UPDATE_MINUTES,
    DEFAULT_KEEP_STALE,
)
from .api import ChatApi
from homeassistant.helpers.update_coordinator import UpdateFailed
from .coordinator_ai import HortiAICoordinator
from .coordinator_local import HortiLocalCoordinator
from .storage import LocalStore
from .utils.paths import ensure_local_data_paths
from aiohttp import ClientError
import asyncio
from .entity_utils import ensure_entities_exist
from .utils.entry_helpers import store_entry_data

SENSORS_SCHEMA = vol.Schema({str: [cv.entity_id]}, extra=vol.PREVENT_EXTRA)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, _config) -> bool:
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
    try:
        await ai_coord.async_config_entry_first_refresh()
        await local_coord.async_config_entry_first_refresh()
    except (UpdateFailed, ClientError, asyncio.TimeoutError) as err:
        _LOGGER.warning("Initial data refresh failed: %s", err)
    except Exception as err:  # pragma: no cover - unexpected
        _LOGGER.exception("Initial data refresh failed: %s", err)
    entry_data = store_entry_data(hass, entry)
    entry_data.update(
        {
            "api": api,
            "coordinator_ai": ai_coord,
            "coordinator_local": local_coord,
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

    async def _handle_refresh(call):
        await ai_coord.async_request_refresh()
        await local_coord.async_request_refresh()

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
        "refresh",
        _handle_refresh,
        schema=vol.Schema({}),
    )
    hass.services.async_register(
        svc_base,
        "update_sensors",
        _handle_update_sensors,
        schema=vol.Schema(
            {vol.Required("plant_id"): str, vol.Required("sensors"): SENSORS_SCHEMA}
        ),
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
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    data = hass.data.get(DOMAIN, {}).pop(entry.entry_id, {})
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
        hass.config_entries.async_update_entry(
            entry, data=data, options=options, version=2
        )
    return True
