from __future__ import annotations
import logging
import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
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
from .coordinator_ai import HortiAICoordinator
from .coordinator_local import HortiLocalCoordinator
from .storage import LocalStore

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
    stored = await store.load()
    minutes = int(
        entry.options.get(
            CONF_UPDATE_INTERVAL,
            entry.data.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_MINUTES),
        )
    )
    keep_stale = entry.options.get(CONF_KEEP_STALE, DEFAULT_KEEP_STALE)
    ai_coord = HortiAICoordinator(
        hass, api, store, update_minutes=minutes, initial=stored.get("recommendation")
    )
    local_coord = HortiLocalCoordinator(hass, store, update_minutes=1)
    try:
        await ai_coord.async_config_entry_first_refresh()
        await local_coord.async_config_entry_first_refresh()
    except Exception:  # UpdateFailed, network errors
        pass
    hass.data[DOMAIN][entry.entry_id] = {
        "api": api,
        "coordinator_ai": ai_coord,
        "coordinator_local": local_coord,
        "store": store,
        "keep_stale": keep_stale,
    }
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _LOGGER.info("Horticulture Assistant setup complete")

    # Validate configured sensors exist
    for key in (CONF_MOISTURE_SENSOR, CONF_TEMPERATURE_SENSOR, CONF_EC_SENSOR, CONF_CO2_SENSOR):
        entity_id = entry.options.get(key)
        if entity_id and hass.states.get(entity_id) is None:
            ir.async_create_issue(
                hass,
                DOMAIN,
                f"missing_entity_{entity_id}",
                is_fixable=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key="missing_entity_option",
                translation_placeholders={"entity_id": entity_id},
            )

    async def _handle_refresh(call):
        await ai_coord.async_request_refresh()

    async def _handle_update_sensors(call):
        plant_id = call.data["plant_id"]
        sensors = call.data["sensors"]
        # Check referenced entities exist
        for sensor_ids in sensors.values():
            for entity_id in sensor_ids:
                if hass.states.get(entity_id) is None:
                    ir.async_create_issue(
                        hass,
                        DOMAIN,
                        f"missing_entity_{plant_id}",
                        is_fixable=False,
                        severity=ir.IssueSeverity.WARNING,
                        translation_key="missing_entity",
                        translation_placeholders={"plant_id": plant_id},
                    )
        store.data.setdefault("plants", {})
        store.data["plants"].setdefault(plant_id, {})["sensors"] = sensors
        await store.save()

    async def _handle_recalculate(call):
        # placeholder; could trigger calculations in real implementation
        return None

    async def _handle_run_reco(call):
        await ai_coord.async_request_refresh()

    svc_base = DOMAIN
    hass.services.async_register(
        svc_base,
        "refresh",
        _handle_refresh,
    )
    hass.services.async_register(
        svc_base,
        "update_sensors",
        _handle_update_sensors,
        schema=vol.Schema({vol.Required("plant_id"): str, vol.Required("sensors"): dict}),
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
        schema=vol.Schema({vol.Required("plant_id"): str, vol.Optional("approve", default=False): bool}),
    )
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate old config entries to new version."""
    if entry.version < 2:
        data = {**entry.data}
        options = {**entry.options}
        if CONF_KEEP_STALE not in options:
            options[CONF_KEEP_STALE] = DEFAULT_KEEP_STALE
        hass.config_entries.async_update_entry(entry, data=data, options=options, version=2)
    return True
