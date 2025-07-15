"""
Horticulture Assistant Integration

This is the main initialization file for the Horticulture Assistant custom component
for Home Assistant. It handles core setup and registration.

Author: Traverse Jurcisin & ChatGPT (GPT-4o)
Repo: horticulture-assistant
"""

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

# Load platforms for the integration
PLATFORMS = ["sensor", "binary_sensor", "switch"]

_LOGGER = logging.getLogger(__name__)

DOMAIN = "horticulture_assistant"

async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the integration from configuration.yaml (optional)."""
    _LOGGER.debug("Setting up horticulture_assistant via configuration.yaml (not recommended)")
    return True  # Allow config entries to manage this integration

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up horticulture_assistant from a config entry."""
    _LOGGER.info("Setting up horticulture_assistant from config entry: %s", entry.entry_id)

    # Store the config entry in hass.data for access in other modules
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}
    hass.data[DOMAIN][entry.entry_id] = entry.data

    # Forward entry setup to supported platforms (e.g., sensor.py, switch.py)
    for platform in PLATFORMS:
        _LOGGER.debug("Forwarding setup to platform: %s", platform)
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, platform)
        )

    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Handle removal of an entry."""
    _LOGGER.info("Unloading horticulture_assistant entry: %s", entry.entry_id)

    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, platform)
                for platform in PLATFORMS
            ]
        )
    )

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
        _LOGGER.debug("Successfully unloaded all platforms for horticulture_assistant")

    return unload_ok