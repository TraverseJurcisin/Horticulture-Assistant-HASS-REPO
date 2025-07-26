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

from .const import DOMAIN, PLATFORMS
from .utils.plant_profile_loader import update_profile_sensors


_LOGGER = logging.getLogger(__name__)


async def update_sensors_service(hass: HomeAssistant, call: ServiceCall) -> None:
    """Handle the ``update_sensors`` service call."""
    plant_id = call.data.get("plant_id")
    sensors = call.data.get("sensors")
    if not plant_id or not isinstance(sensors, dict):
        _LOGGER.error("update_sensors called with invalid data")
        return

    base_dir = hass.config.path("plants")
    if update_profile_sensors(plant_id, sensors, base_dir):
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

    # Forward config entry to all supported platforms
    for platform in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, platform)
        )

    # Initialize storage/data if needed and store entry metadata
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "config_entry": entry,
        "plant_id": entry.data.get("plant_id", entry.entry_id),
        "data": dict(entry.data),
    }

    # Register services
    hass.services.async_register(
        DOMAIN,
        "update_sensors",
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
        hass.data[DOMAIN].pop(entry.entry_id, None)

    return all(unload_results)
