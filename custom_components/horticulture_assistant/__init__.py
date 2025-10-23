from __future__ import annotations

import contextlib
import importlib
import importlib.util
import logging

import homeassistant.helpers.config_validation as cv
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from . import services as ha_services
from .api import ChatApi
from .cloudsync import CloudSyncManager, CloudSyncPublisher
from .const import (
    CONF_API_KEY,
    CONF_BASE_URL,
    CONF_KEEP_STALE,
    CONF_MODEL,
    CONF_PLANT_ID,
    CONF_PROFILES,
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
from .http import async_register_http_views
from .profile_registry import ProfileRegistry
from .profile_store import ProfileStore
from .storage import LocalStore
from .utils.entry_helpers import remove_entry_data, store_entry_data
from .utils.paths import ensure_local_data_paths

_CALIBRATION_SPEC = importlib.util.find_spec("custom_components.horticulture_assistant.calibration.services")
calibration_services = None
if _CALIBRATION_SPEC is not None:
    calibration_services = importlib.import_module("custom_components.horticulture_assistant.calibration.services")

__all__ = [
    "async_setup",
    "async_setup_entry",
    "async_unload_entry",
]

_LOGGER = logging.getLogger(__name__)
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(_hass: HomeAssistant, _config: dict) -> bool:
    """Set up the integration using YAML is not supported."""

    _LOGGER.debug("async_setup called: configuration entries only")
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Horticulture Assistant from a ConfigEntry."""

    await ensure_local_data_paths(hass)
    base_url = entry.options.get(CONF_BASE_URL, entry.data.get(CONF_BASE_URL, DEFAULT_BASE_URL))
    api_key = entry.options.get(CONF_API_KEY, entry.data.get(CONF_API_KEY, ""))
    model = entry.options.get(CONF_MODEL, entry.data.get(CONF_MODEL, DEFAULT_MODEL))
    keep_stale = entry.options.get(CONF_KEEP_STALE, entry.data.get(CONF_KEEP_STALE, DEFAULT_KEEP_STALE))
    update_minutes = entry.options.get(
        CONF_UPDATE_INTERVAL,
        entry.data.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_MINUTES),
    )

    api = ChatApi(hass, api_key, base_url, model)

    local_store = LocalStore(hass)
    await local_store.load()

    profile_store = ProfileStore(hass)
    await profile_store.async_init()

    cloud_sync_manager = CloudSyncManager(hass, entry)

    profile_registry = ProfileRegistry(hass, entry)
    await profile_registry.async_initialize()
    cloud_publisher = CloudSyncPublisher(cloud_sync_manager, entry.entry_id)
    profile_registry.attach_cloud_publisher(cloud_publisher)

    coordinator = HorticultureCoordinator(
        hass,
        entry.entry_id,
        {
            CONF_PROFILES: entry.options.get(CONF_PROFILES, {}),
        },
    )
    await coordinator.async_config_entry_first_refresh()

    ai_coordinator = HortiAICoordinator(
        hass,
        api,
        local_store,
        update_minutes,
        (local_store.data or {}).get("recommendation") if local_store.data else None,
    )
    local_coordinator = HortiLocalCoordinator(
        hass,
        local_store,
        update_minutes,
    )

    entry_data = store_entry_data(hass, entry)
    entry_data.update(
        {
            "api": api,
            "profile_store": profile_store,
            "profile_registry": profile_registry,
            "profiles": profile_registry,
            "registry": profile_registry,
            "local_store": local_store,
            "coordinator": coordinator,
            "coordinator_ai": ai_coordinator,
            "coordinator_local": local_coordinator,
            "keep_stale": keep_stale,
            "cloud_sync_manager": cloud_sync_manager,
            "cloud_sync_status": cloud_sync_manager.status(),
            "cloud_publisher": cloud_publisher,
        }
    )

    async_register_http_views(hass)

    await cloud_sync_manager.async_start()
    entry_data["cloud_sync_status"] = cloud_sync_manager.status()

    domain_data = hass.data.setdefault(DOMAIN, {})
    domain_data["registry"] = profile_registry

    sensors = entry.options.get("sensors")
    if isinstance(sensors, dict) and sensors:
        sensor_ids = [value for value in sensors.values() if isinstance(value, str)]
        if sensor_ids:
            ensure_entities_exist(
                hass,
                entry.data.get(CONF_PLANT_ID, entry.entry_id),
                sensor_ids,
            )

    profile_options = entry.options.get(CONF_PROFILES, {})
    if isinstance(profile_options, dict):
        for profile_id, profile_data in profile_options.items():
            profile_sensors = []
            if isinstance(profile_data, dict):
                sensor_map = profile_data.get("sensors", {})
                if isinstance(sensor_map, dict):
                    profile_sensors = [value for value in sensor_map.values() if isinstance(value, str)]
            if profile_sensors:
                ensure_entities_exist(
                    hass,
                    profile_id,
                    profile_sensors,
                    placeholders={
                        "plant_id": profile_id,
                        "profile_name": profile_data.get("name", profile_id)
                        if isinstance(profile_data, dict)
                        else profile_id,
                    },
                )

    await ha_services.async_register_all(
        hass,
        entry,
        ai_coordinator,
        local_coordinator,
        coordinator,
        profile_registry,
        local_store,
        cloud_manager=cloud_sync_manager,
    )
    ha_services.async_setup_services(hass)
    if calibration_services is not None:
        calibration_services.async_setup_services(hass)

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a ConfigEntry."""

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        data = hass.data.get(DOMAIN, {})
        info = data.pop(entry.entry_id, None)
        if info:
            manager = info.get("cloud_sync_manager")
            if manager and hasattr(manager, "async_stop"):
                with contextlib.suppress(Exception):
                    await manager.async_stop()
            profiles = info.get("profiles")
            if profiles and hasattr(profiles, "async_unload"):
                with contextlib.suppress(Exception):
                    await profiles.async_unload()
        remove_entry_data(hass, entry.entry_id)
    return unload_ok
