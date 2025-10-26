"""Helpers for working with integration config entries."""

from collections.abc import Mapping
from pathlib import Path
from typing import Any

try:  # pragma: no cover - allow running tests without Home Assistant
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
except (ModuleNotFoundError, ImportError):
    ConfigEntry = object  # type: ignore
    HomeAssistant = object  # type: ignore

from ..const import CONF_PLANT_ID, CONF_PLANT_NAME, CONF_PROFILES, DOMAIN

# Keys used under ``hass.data[DOMAIN]``
BY_PLANT_ID = "by_plant_id"


def get_entry_plant_info(entry: ConfigEntry) -> tuple[str, str]:
    """Return ``(plant_id, plant_name)`` for a config entry."""

    primary_id = get_primary_profile_id(entry)
    plant_id = primary_id or entry.data.get(CONF_PLANT_ID) or entry.entry_id

    profile = get_primary_profile_options(entry)
    if profile:
        name = profile.get("name")
        if isinstance(name, str) and name.strip():
            return plant_id, name.strip()

    data_name = entry.data.get(CONF_PLANT_NAME)
    if isinstance(data_name, str) and data_name.strip():
        return plant_id, data_name.strip()

    return plant_id, f"Plant {plant_id[:6]}"


def _coerce_mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, Mapping):
        return {str(key): item for key, item in value.items()}
    return {}


def _normalise_sensor_map(value: Any) -> dict[str, str]:
    sensors = {}
    mapping = _coerce_mapping(value)
    for key, item in mapping.items():
        if isinstance(item, str) and item:
            sensors[str(key)] = item
    return sensors


def get_primary_profile_id(entry: ConfigEntry) -> str | None:
    """Return the profile id most closely associated with ``entry``."""

    plant_id = entry.data.get(CONF_PLANT_ID)
    if isinstance(plant_id, str) and plant_id:
        return plant_id

    opt_pid = entry.options.get(CONF_PLANT_ID) if isinstance(entry.options, Mapping) else None
    if isinstance(opt_pid, str) and opt_pid:
        return opt_pid

    profiles = entry.options.get(CONF_PROFILES)
    if isinstance(profiles, Mapping):
        for key, value in profiles.items():
            if isinstance(key, str) and key and isinstance(value, Mapping):
                return key

    return None


def get_primary_profile_options(entry: ConfigEntry) -> dict[str, Any]:
    """Return the options payload for the primary profile if available."""

    profiles = entry.options.get(CONF_PROFILES)
    if not isinstance(profiles, Mapping):
        return {}

    plant_id = get_primary_profile_id(entry)
    if plant_id and isinstance(profiles.get(plant_id), Mapping):
        return _coerce_mapping(profiles[plant_id])

    for payload in profiles.values():
        if isinstance(payload, Mapping):
            return _coerce_mapping(payload)

    return {}


def get_primary_profile_sensors(entry: ConfigEntry) -> dict[str, str]:
    """Return the canonical sensor mapping for the entry's primary profile."""

    sensors = _normalise_sensor_map(entry.options.get("sensors"))
    if sensors:
        return sensors

    profile = get_primary_profile_options(entry)
    sensors = _normalise_sensor_map(profile.get("sensors"))
    if sensors:
        return sensors

    general = profile.get("general") if isinstance(profile.get("general"), Mapping) else {}
    sensors = _normalise_sensor_map(general.get("sensors")) if isinstance(general, Mapping) else {}
    return sensors


def get_primary_profile_thresholds(entry: ConfigEntry) -> dict[str, Any]:
    """Return threshold values for the entry's primary profile."""

    thresholds = entry.options.get("thresholds") if isinstance(entry.options, Mapping) else {}
    if isinstance(thresholds, Mapping) and thresholds:
        return _coerce_mapping(thresholds)

    profile = get_primary_profile_options(entry)
    thresholds_map = profile.get("thresholds") if isinstance(profile.get("thresholds"), Mapping) else {}
    if isinstance(thresholds_map, Mapping) and thresholds_map:
        return _coerce_mapping(thresholds_map)

    resolved = profile.get("resolved_targets") if isinstance(profile.get("resolved_targets"), Mapping) else {}
    computed: dict[str, Any] = {}
    if isinstance(resolved, Mapping):
        for key, value in resolved.items():
            if isinstance(value, Mapping) and "value" in value:
                computed[str(key)] = value["value"]
    if computed:
        return computed

    variables = profile.get("variables") if isinstance(profile.get("variables"), Mapping) else {}
    if isinstance(variables, Mapping):
        for key, value in variables.items():
            if isinstance(value, Mapping) and "value" in value:
                computed[str(key)] = value["value"]
    return computed


def build_entry_snapshot(entry: ConfigEntry) -> dict[str, Any]:
    """Return a normalised snapshot of the entry's profile context."""

    primary_id = get_primary_profile_id(entry)
    plant_id, plant_name = get_entry_plant_info(entry)
    primary_profile = get_primary_profile_options(entry)
    sensors = get_primary_profile_sensors(entry)
    thresholds = get_primary_profile_thresholds(entry)

    profiles: dict[str, dict[str, Any]] = {}
    raw_profiles = entry.options.get(CONF_PROFILES)
    if isinstance(raw_profiles, Mapping):
        for pid, payload in raw_profiles.items():
            if not isinstance(pid, str) or not pid:
                continue
            if isinstance(payload, Mapping):
                profiles[pid] = _coerce_mapping(payload)

    return {
        "plant_id": plant_id,
        "plant_name": plant_name,
        "primary_profile_id": primary_id or plant_id,
        "primary_profile_name": plant_name,
        "primary_profile": primary_profile,
        "profiles": profiles,
        "sensors": sensors,
        "thresholds": thresholds,
    }


def store_entry_data(hass: HomeAssistant, entry: ConfigEntry) -> dict:
    """Store entry metadata under ``hass.data`` and return it."""
    data = hass.data.setdefault(DOMAIN, {})
    by_pid = data.setdefault(BY_PLANT_ID, {})
    entry_data: dict[str, Any] = {"config_entry": entry}
    data[entry.entry_id] = entry_data
    return update_entry_data(hass, entry, entry_data=entry_data, by_pid=by_pid)


def update_entry_data(
    hass: HomeAssistant,
    entry: ConfigEntry,
    *,
    entry_data: dict[str, Any] | None = None,
    by_pid: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Refresh stored metadata for ``entry`` and return it."""

    domain_data = hass.data.setdefault(DOMAIN, {})
    if entry_data is None:
        entry_data = domain_data.setdefault(entry.entry_id, {"config_entry": entry})
    else:
        domain_data[entry.entry_id] = entry_data

    snapshot = build_entry_snapshot(entry)

    previous_id = entry_data.get("plant_id")
    entry_data.update(
        {
            "config_entry": entry,
            "plant_id": snapshot["plant_id"],
            "plant_name": snapshot["plant_name"],
            "primary_profile_id": snapshot.get("primary_profile_id"),
            "primary_profile_name": snapshot.get("primary_profile_name"),
            "snapshot": snapshot,
            "data": dict(entry.data),
            "profile_dir": Path(hass.config.path("plants")) / snapshot["plant_id"],
        }
    )

    if by_pid is None:
        by_pid = domain_data.setdefault(BY_PLANT_ID, {})
    if previous_id and previous_id != snapshot["plant_id"]:
        if by_pid.get(previous_id) is entry_data:
            by_pid.pop(previous_id, None)
    by_pid[snapshot["plant_id"]] = entry_data
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
            set(domain_data.keys()) <= {BY_PLANT_ID} and not domain_data.get(BY_PLANT_ID)
        ):
            hass.data.pop(DOMAIN, None)


def get_entry_data(hass: HomeAssistant, entry_or_id: ConfigEntry | str) -> dict | None:
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
