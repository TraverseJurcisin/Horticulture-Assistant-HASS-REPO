"""Helpers for working with integration config entries."""

from pathlib import Path

try:  # pragma: no cover - allow running tests without Home Assistant
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
except (ModuleNotFoundError, ImportError):
    ConfigEntry = object  # type: ignore
    HomeAssistant = object  # type: ignore

from ..const import DOMAIN

# Keys used under ``hass.data[DOMAIN]``
BY_PLANT_ID = "by_plant_id"


def get_entry_plant_info(entry: ConfigEntry) -> tuple[str, str]:
    """Return ``(plant_id, plant_name)`` for a config entry."""
    plant_id = entry.data.get("plant_id", entry.entry_id)
    plant_name = entry.data.get("plant_name", f"Plant {plant_id[:6]}")
    return plant_id, plant_name


def store_entry_data(hass: HomeAssistant, entry: ConfigEntry) -> dict:
    """Store entry metadata under ``hass.data`` and return it."""
    plant_id, plant_name = get_entry_plant_info(entry)
    data = hass.data.setdefault(DOMAIN, {})
    by_pid = data.setdefault(BY_PLANT_ID, {})
    entry_data = {
        "config_entry": entry,
        "plant_id": plant_id,
        "plant_name": plant_name,
        "profile_dir": Path(hass.config.path("plants")) / plant_id,
        "data": dict(entry.data),
    }
    data[entry.entry_id] = entry_data
    by_pid[plant_id] = entry_data
    return entry_data


def remove_entry_data(hass: HomeAssistant, entry_id: str) -> None:
    """Remove stored metadata for ``entry_id`` if present."""
    domain_data = hass.data.get(DOMAIN)
    if domain_data is not None:
        entry_data = domain_data.pop(entry_id, None)
        if entry_data:
            plant_id = entry_data.get("plant_id")
            by_pid = domain_data.get(BY_PLANT_ID)
            if by_pid and by_pid.get(plant_id) is entry_data:
                by_pid.pop(plant_id, None)
        if not domain_data or (
            set(domain_data.keys()) <= {BY_PLANT_ID}
            and not domain_data.get(BY_PLANT_ID)
        ):
            hass.data.pop(DOMAIN, None)


def get_entry_data(
    hass: HomeAssistant, entry_or_id: ConfigEntry | str
) -> dict | None:
    """Return stored entry metadata or ``None`` if missing."""
    entry_id = getattr(entry_or_id, "entry_id", entry_or_id)
    data = hass.data.get(DOMAIN, {})
    stored = data.get(entry_id)
    if stored is None and entry_id in data.get(BY_PLANT_ID, {}):
        stored = data[BY_PLANT_ID][entry_id]
    return stored


def get_entry_data_by_plant_id(hass: HomeAssistant, plant_id: str) -> dict | None:
    """Return stored entry metadata looked up by ``plant_id``."""
    return hass.data.get(DOMAIN, {}).get(BY_PLANT_ID, {}).get(plant_id)
