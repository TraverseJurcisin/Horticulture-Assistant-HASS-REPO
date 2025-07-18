"""
Horticulture Assistant: 
Custom integration init module.

This is the main initialization file for the Horticulture Assistant custom component
for Home Assistant. It handles core setup and registration.

Author: Traverse Jurcisin & ChatGPT (GPT-4o)
Repo: horticulture-assistant
"""

import logging

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Horticulture Assistant integration via YAML (if used)."""
    _LOGGER.debug("async_setup (YAML) called, but this integration uses UI config flows.")
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Horticulture Assistant from a config entry."""
    _LOGGER.info("Setting up Horticulture Assistant from config entry: %s", entry.entry_id)

    # Forward config entry to the platforms defined in manifest.json
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "sensor")
    )

    # Initialize storage/data if needed
    hass.data.setdefault(DOMAIN, {})

    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.info("Unloading Horticulture Assistant config entry: %s", entry.entry_id)
    unload_ok = await hass.config_entries.async_forward_entry_unload(entry, "sensor")

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)

    return unload_ok