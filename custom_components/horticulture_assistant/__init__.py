from __future__ import annotations

import contextlib
import logging

import voluptuous as vol

try:
    import homeassistant.helpers.config_validation as cv
except ModuleNotFoundError:  # pragma: no cover - test fallback
    cv = None

try:
    from aiohttp import ClientError, ClientResponseError
except ModuleNotFoundError:  # pragma: no cover - test fallback

    class ClientError(Exception):
        """Fallback ClientError used when aiohttp is unavailable."""

    class ClientResponseError(ClientError):
        """Fallback ClientResponseError used when aiohttp is unavailable."""


try:
    from homeassistant.config_entries import ConfigEntry
except ModuleNotFoundError:  # pragma: no cover - test fallback
    ConfigEntry = object

try:
    from homeassistant.core import HomeAssistant
except ModuleNotFoundError:  # pragma: no cover - test fallback
    HomeAssistant = object

try:
    from homeassistant.helpers.update_coordinator import UpdateFailed
except ModuleNotFoundError:  # pragma: no cover - test fallback
    UpdateFailed = Exception

from . import services as ha_services
from .api import ChatApi

try:
    from .calibration import services as calibration_services
except ModuleNotFoundError:  # pragma: no cover - optional dependency missing
    calibration_services = None
from .const import (
    CONF_API_KEY,
    CONF_BASE_URL,
    CONF_KEEP_STALE,
    CONF_MODEL,
    CONF_UPDATE_INTERVAL,
    CONF_PLANT_ID,
    CONF_PROFILES,
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
from .profile_store import ProfileStore
from .storage import LocalStore
from .utils.paths import ensure_local_data_paths

__all__ = [
    "async_setup",
    "async_setup_entry",
    "async_unload_entry",
]

_LOGGER = logging.getLogger(__name__)


if cv is not None:
    CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
else:
    CONFIG_SCHEMA = vol.Schema({DOMAIN: vol.Schema({})}, extra=vol.ALLOW_EXTRA)


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

    profile_registry = ProfileRegistry(hass, LocalStore(hass, entry))
    await profile_registry.async_initialize()

    profile_store = ProfileStore(hass)
    await profile_store.async_init()

    coordinator = HorticultureCoordinator(
        hass,
        api,
        profile_registry,
        keep_stale,
    )
    await coordinator.async_config_entry_first_refresh()

    ai_coordinator = HortiAICoordinator(
        hass,
        api,
        profile_registry,
        model,
    )
    local_coordinator = HortiLocalCoordinator(
        hass,
        profile_registry,
        update_minutes,
    )

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "api": api,
        "profiles": profile_registry,
        "registry": profile_registry,
        "profile_store": profile_store,
        "coordinator": coordinator,
        "ai": ai_coordinator,
        "local": local_coordinator,
    }

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
            with contextlib.suppress(Exception):
                await info["profiles"].async_unload()
    return unload_ok
