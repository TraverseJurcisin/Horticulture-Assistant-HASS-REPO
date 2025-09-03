from __future__ import annotations

import contextlib
import logging

import homeassistant.helpers.config_validation as cv
from aiohttp import ClientError
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
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
from .profile_registry import ProfileRegistry
from .storage import LocalStore
from .utils.entry_helpers import store_entry_data
from .utils.paths import ensure_local_data_paths

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
    ai_coord = HortiAICoordinator(hass, api, store, update_minutes=minutes, initial=stored.get("recommendation"))
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
    if not hass.services.has_service(DOMAIN, "refresh"):
        await ha_services.async_register_all(
            hass=hass,
            entry=entry,
            ai_coord=ai_coord,
            local_coord=local_coord,
            profile_coord=profile_coord,
            registry=registry,
            store=store,
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

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    data = hass.data.get(DOMAIN, {}).pop(entry.entry_id, {})
    unsub = data.get("opb_unsub")
    if unsub:
        with contextlib.suppress(Exception):  # pragma: no cover - best effort cleanup
            unsub()
    for key in ("coordinator_ai", "coordinator_local", "coordinator"):
        coord = data.get(key)
        if coord and hasattr(coord, "async_shutdown"):
            with contextlib.suppress(Exception):  # pragma: no cover - best effort cleanup
                await coord.async_shutdown()
    if not hass.config_entries.async_entries(DOMAIN):
        await ha_services.async_unregister_all(hass)
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
