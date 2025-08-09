from __future__ import annotations
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from .const import (
    DOMAIN, PLATFORMS, CONF_API_KEY, CONF_MODEL, CONF_BASE_URL, CONF_UPDATE_INTERVAL,
    DEFAULT_BASE_URL, DEFAULT_MODEL, DEFAULT_UPDATE_MINUTES
)
from .api import ChatApi
from .coordinator import HortiCoordinator
from .storage import LocalStore

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
    coord = HortiCoordinator(
        hass, api, store, update_minutes=minutes, initial=stored.get("recommendation")
    )
    await coord.async_config_entry_first_refresh()
    hass.data[DOMAIN][entry.entry_id] = {"api": api, "coordinator": coord, "store": store}
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok
