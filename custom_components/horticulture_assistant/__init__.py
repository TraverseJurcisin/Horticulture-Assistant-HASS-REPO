"""
Horticulture Assistant integration entry module.

This file sets up the custom component within Home Assistant and forwards the
configuration entry to the supported platforms. It is intentionally minimal as
all heavy lifting happens in the individual platform modules.

Author: Traverse Jurcisin & ChatGPT (GPT-4o)
Repo: horticulture-assistant
"""

import logging

import asyncio
from functools import partial

try:
    from homeassistant.core import HomeAssistant, ServiceCall
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.helpers.typing import ConfigType

except (ModuleNotFoundError, ImportError):  # pragma: no cover
    # Allow running tests without Home Assistant installed
    HomeAssistant = object  # type: ignore
    ServiceCall = object  # type: ignore
    ConfigEntry = object  # type: ignore
    ConfigType = dict

from .const import DOMAIN, PLATFORMS, SERVICE_UPDATE_SENSORS
from .utils.entry_helpers import (
    store_entry_data,
    remove_entry_data,
)
from .utils.plant_profile_loader import update_profile_sensors
from .utils.path_utils import plants_path


_LOGGER = logging.getLogger(__name__)


async def update_sensors_service(
    hass: HomeAssistant, call: ServiceCall
) -> None:
    """Handle the ``update_sensors`` service call."""
    plant_id = call.data.get("plant_id")
    sensors = call.data.get("sensors")
    if not plant_id or not isinstance(sensors, dict):
        _LOGGER.error("update_sensors called with invalid data")
        return

    base_dir = plants_path(hass)
    # Run blocking disk IO in a thread so we don't slow the event loop
    result = await asyncio.to_thread(
        update_profile_sensors, plant_id, sensors, base_dir
    )
    if result:
        _LOGGER.info("Updated sensors for profile %s", plant_id)
    else:
        _LOGGER.error("Failed to update sensors for profile %s", plant_id)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Horticulture Assistant integration via YAML (if used)."""
    _LOGGER.debug(
        "async_setup (YAML) called, but this integration uses UI config flows."
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Horticulture Assistant from a config entry."""
    _LOGGER.info(
        "Initializing Horticulture Assistant from entry: %s", entry.entry_id
    )

    # Initialize storage/data so platforms can access it during their setup
    store_entry_data(hass, entry)

    # Forward config entry to all supported platforms
    for platform in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, platform)
        )

    # Register services once
    if not hass.services.has_service(DOMAIN, SERVICE_UPDATE_SENSORS):
        hass.services.async_register(
            DOMAIN,
            SERVICE_UPDATE_SENSORS,
            partial(update_sensors_service, hass),
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.info(
        "Unloading Horticulture Assistant config entry: %s", entry.entry_id
    )
    unload_results = await asyncio.gather(
        *[
            hass.config_entries.async_forward_entry_unload(entry, platform)
            for platform in PLATFORMS
        ]
    )

    if all(unload_results):
        remove_entry_data(hass, entry.entry_id)
        if not hass.data.get(DOMAIN):
            if hass.services.has_service(DOMAIN, SERVICE_UPDATE_SENSORS):
                hass.services.async_remove(DOMAIN, SERVICE_UPDATE_SENSORS)

    return all(unload_results)
