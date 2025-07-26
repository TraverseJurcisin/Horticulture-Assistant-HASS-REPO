"""Helpers for working with integration config entries."""

try:  # pragma: no cover - allow running tests without Home Assistant
    from homeassistant.config_entries import ConfigEntry
except (ModuleNotFoundError, ImportError):
    ConfigEntry = object  # type: ignore


def get_entry_plant_info(entry: ConfigEntry) -> tuple[str, str]:
    """Return ``(plant_id, plant_name)`` for a config entry."""
    plant_id = entry.data.get("plant_id", entry.entry_id)
    plant_name = entry.data.get("plant_name", f"Plant {plant_id[:6]}")
    return plant_id, plant_name
