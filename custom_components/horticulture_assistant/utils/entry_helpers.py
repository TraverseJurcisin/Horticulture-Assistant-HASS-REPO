"""Helpers for working with integration config entries."""

from pathlib import Path

try:  # pragma: no cover - allow running tests without Home Assistant
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
except (ModuleNotFoundError, ImportError):
    ConfigEntry = object  # type: ignore
    HomeAssistant = object  # type: ignore

from ..const import DOMAIN


def get_entry_plant_info(entry: ConfigEntry) -> tuple[str, str]:
    """Return ``(plant_id, plant_name)`` for a config entry."""
    plant_id = entry.data.get("plant_id", entry.entry_id)
    plant_name = entry.data.get("plant_name", f"Plant {plant_id[:6]}")
    return plant_id, plant_name


def store_entry_data(hass: HomeAssistant, entry: ConfigEntry) -> dict:
    """Store entry metadata under ``hass.data`` and return it."""
    plant_id, plant_name = get_entry_plant_info(entry)
    data = hass.data.setdefault(DOMAIN, {})
    entry_data = {
        "config_entry": entry,
        "plant_id": plant_id,
        "plant_name": plant_name,
        "profile_dir": Path(hass.config.path("plants")) / plant_id,
        "data": dict(entry.data),
    }
    data[entry.entry_id] = entry_data
    return entry_data


def remove_entry_data(hass: HomeAssistant, entry_id: str) -> None:
    """Remove stored metadata for ``entry_id`` if present."""
    domain_data = hass.data.get(DOMAIN)
    if domain_data is not None:
        domain_data.pop(entry_id, None)
