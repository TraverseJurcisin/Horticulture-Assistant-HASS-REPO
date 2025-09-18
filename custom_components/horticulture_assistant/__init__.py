from __future__ import annotations

import contextlib
import logging

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
    CONF_BASE_URL,
    CONF_KEEP_STALE,
    CONF_MODEL,
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
from .profile_store import ProfileStore
from .storage import LocalStore
from .utils.paths import ensure_local_data_paths

__all__ = [
    "async_setup",
    "async_setup_entry",
    "async_unload_entry",
]

_LOGGER = logging.getLogger(__name__)


async def async_setup(_hass: HomeAssistant, _config: dict) -> bool:
    """Set up the integration using YAML is not supported."""

    _LOGGER.debug("async_setup called: configuration entries only")
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Horticulture Assistant from a ConfigEntry."""

    ensure_local_data_paths()

    api = ChatApi(hass, entry.data.get(CONF_BASE_URL, DEFAULT_BASE_URL))

    profile_registry = ProfileRegistry(hass, LocalStore(hass, entry))
    await profile_registry.async_initialize()

    profile_store = ProfileStore(hass)
    await profile_store.async_init()

    coordinator = HorticultureCoordinator(
        hass,
        api,
        profile_registry,
        entry.data.get(CONF_KEEP_STALE, DEFAULT_KEEP_STALE),
    )
    await coordinator.async_config_entry_first_refresh()

    ai_coordinator = HortiAICoordinator(
        hass,
        api,
        profile_registry,
        entry.data.get(CONF_MODEL, DEFAULT_MODEL),
    )
    local_coordinator = HortiLocalCoordinator(
        hass,
        profile_registry,
        entry.data.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_MINUTES),
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

    await ensure_entities_exist(
        hass,
        coordinator,
        entry.options,
        entry.data,
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
