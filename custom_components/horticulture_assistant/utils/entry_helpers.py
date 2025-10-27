"""Helpers for working with integration config entries."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any, Iterator

import types

try:  # pragma: no cover - allow running tests without Home Assistant
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
except (ModuleNotFoundError, ImportError):
    ConfigEntry = object  # type: ignore
    HomeAssistant = object  # type: ignore

try:  # pragma: no cover - allow running tests without Home Assistant
    from homeassistant.helpers import device_registry as dr
except (ModuleNotFoundError, ImportError):  # pragma: no cover - executed in stubbed env

    class _DeviceRegistryStub:
        """Minimal stand-in used when Home Assistant is unavailable."""

        devices: dict[str, Any] = {}

        def async_get_or_create(self, **_kwargs):
            return types.SimpleNamespace(id="stub")

        def async_remove_device(self, *_args, **_kwargs):
            return None

        def async_get_device(self, *_args, **_kwargs):  # pragma: no cover - basic stub
            return None

    dr = types.SimpleNamespace(async_get=lambda _hass: _DeviceRegistryStub())  # type: ignore[assignment]

from ..const import CONF_PLANT_ID, CONF_PLANT_NAME, CONF_PROFILES, DOMAIN

# Keys used under ``hass.data[DOMAIN]``
BY_PLANT_ID = "by_plant_id"


def _mapping_proxy(payload: Mapping[str, Any] | None) -> Mapping[str, Any]:
    """Return a read-only mapping preserving Home Assistant payload semantics."""

    if isinstance(payload, MappingProxyType):
        return payload
    if isinstance(payload, Mapping):
        return MappingProxyType(dict(payload))
    return MappingProxyType({})


def _normalise_sensor_sequences(
    value: Mapping[str, Any] | None,
) -> dict[str, tuple[str, ...]]:
    """Return a deterministic mapping of sensor role -> entity ids."""

    sensors: dict[str, tuple[str, ...]] = {}
    if not isinstance(value, Mapping):
        return sensors

    for key, raw in value.items():
        if not isinstance(key, str) or not key:
            continue
        if isinstance(raw, str):
            items = (raw,) if raw else tuple()
        elif isinstance(raw, Sequence):
            items = tuple(
                item for item in raw if isinstance(item, str) and item
            )
        else:
            items = tuple()
        if items:
            sensors[key] = items
    return sensors


@dataclass(frozen=True, slots=True)
class ProfileContext:
    """Runtime metadata describing a plant profile and its device."""

    id: str
    name: str
    sensors: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    thresholds: Mapping[str, Any] = field(default_factory=dict)
    payload: Mapping[str, Any] = field(default_factory=dict)
    device_info: Mapping[str, Any] = field(default_factory=dict)
    image_url: str | None = None

    def __post_init__(self) -> None:  # pragma: no cover - exercised indirectly
        sensors = _normalise_sensor_sequences(self.sensors)
        thresholds = _coerce_mapping(self.thresholds)
        payload = _coerce_mapping(self.payload)
        device = _clean_device_kwargs(_normalise_device_info(self.device_info))
        object.__setattr__(self, "sensors", MappingProxyType(sensors))
        object.__setattr__(self, "thresholds", MappingProxyType(thresholds))
        object.__setattr__(self, "payload", MappingProxyType(payload))
        object.__setattr__(self, "device_info", MappingProxyType(dict(device)))
        image = self.image_url if isinstance(self.image_url, str) else None
        object.__setattr__(self, "image_url", image)

    def sensor_ids_for_roles(self, *roles: str) -> tuple[str, ...]:
        """Return the configured entity ids for ``roles`` preserving order."""

        if not roles:
            return tuple(id_ for ids in self.sensors.values() for id_ in ids)
        collected: list[str] = []
        for role in roles:
            collected.extend(self.sensors.get(role, ()))
        return tuple(collected)

    def first_sensor(self, role: str) -> str | None:
        """Return the first entity id configured for ``role`` if present."""

        sensors = self.sensors.get(role)
        return sensors[0] if sensors else None

    def has_sensors(self, *roles: str) -> bool:
        """Return ``True`` when at least one entity id is available for ``roles``."""

        if not roles:
            return bool(self.sensors)
        return all(self.sensors.get(role) for role in roles)

    def get_threshold(self, key: str, default: Any | None = None) -> Any | None:
        """Return a stored threshold value for ``key`` if available."""

        return self.thresholds.get(key, default)

    def as_device_info(self) -> dict[str, Any]:
        """Return a copy of the Home Assistant device info payload."""

        return dict(self.device_info)


@dataclass(frozen=True, slots=True)
class ProfileContextCollection:
    """Container aggregating profile contexts for an integration entry."""

    entry: ConfigEntry
    stored: Mapping[str, Any]
    contexts: Mapping[str, ProfileContext]
    plant_id: str
    plant_name: str
    primary_id: str

    def __post_init__(self) -> None:  # pragma: no cover - exercised indirectly
        object.__setattr__(self, "stored", _mapping_proxy(self.stored))
        object.__setattr__(self, "contexts", MappingProxyType(dict(self.contexts)))
        object.__setattr__(self, "plant_id", str(self.plant_id))
        object.__setattr__(self, "plant_name", str(self.plant_name))
        object.__setattr__(self, "primary_id", str(self.primary_id))

    @property
    def entry_id(self) -> str | None:
        """Return the config entry identifier."""

        return getattr(self.entry, "entry_id", None)

    @property
    def primary(self) -> ProfileContext:
        """Return the primary profile context for the collection."""

        context = self.contexts.get(self.primary_id)
        if context is not None:
            return context
        if self.contexts:
            return next(iter(self.contexts.values()))
        raise KeyError("No profile contexts available")

    def get(self, profile_id: str) -> ProfileContext | None:
        """Return the context for ``profile_id`` if available."""

        return self.contexts.get(profile_id)

    def values(self) -> Iterator[ProfileContext]:
        """Iterate over stored profile contexts preserving insertion order."""

        return iter(self.contexts.values())

    def items(self) -> Iterator[tuple[str, ProfileContext]]:
        """Iterate over ``(profile_id, context)`` pairs."""

        return iter(self.contexts.items())


def entry_device_key(entry_id: str | None) -> str:
    """Return the device identifier key for a config entry."""

    if not entry_id:
        return "entry:unknown"
    entry_id = str(entry_id)
    return f"entry:{entry_id}"


def profile_device_key(entry_id: str | None, profile_id: str | None) -> str:
    """Return the device identifier key for a profile bound to ``entry_id``."""

    profile = str(profile_id or "profile")
    if entry_id:
        return f"{entry_id}:profile:{profile}"
    return f"profile:{profile}"


def entry_device_identifier(entry_id: str | None) -> tuple[str, str]:
    """Return the tuple identifier for the entry device."""

    return (DOMAIN, entry_device_key(entry_id))


def profile_device_identifier(entry_id: str | None, profile_id: str | None) -> tuple[str, str]:
    """Return the tuple identifier for a profile device."""

    return (DOMAIN, profile_device_key(entry_id, profile_id))


def _normalise_device_info(info: Mapping[str, Any] | None) -> dict[str, Any]:
    if not isinstance(info, Mapping):
        return {}
    payload = dict(info)
    identifiers = payload.get("identifiers")
    if identifiers:
        payload["identifiers"] = _coerce_device_identifiers(identifiers)
    else:
        payload["identifiers"] = set()
    connections = payload.get("connections")
    if connections:
        payload["connections"] = _coerce_device_identifiers(connections)
    return payload


def _clean_device_kwargs(info: Mapping[str, Any]) -> dict[str, Any]:
    clean: dict[str, Any] = {}
    for key, value in info.items():
        if value is None:
            continue
        if key in {"identifiers", "connections"}:
            if not value:
                continue
            if not isinstance(value, set):
                value = _coerce_device_identifiers(value)
            clean[key] = value
            continue
        clean[key] = value
    return clean


def _serialise_identifier(value: Any) -> str | list[str]:
    """Return ``value`` coerced into a JSON-friendly identifier."""

    if isinstance(value, tuple | list) and len(value) == 2:
        return [str(value[0]), str(value[1])]
    return str(value)


def _serialise_identifier_set(values: Iterable[Any]) -> list[str | list[str]]:
    serialised = [_serialise_identifier(item) for item in values]

    def _key(item: str | list[str]) -> tuple[str, str]:
        if isinstance(item, list) and item:
            second = item[1] if len(item) > 1 else ""
            return str(item[0]), str(second)
        return str(item), ""

    return sorted(serialised, key=_key)


def _profile_payload_from_snapshot(snapshot: Mapping[str, Any] | None, profile_id: str) -> dict[str, Any]:
    if not isinstance(snapshot, Mapping):
        return {}
    profiles = snapshot.get("profiles")
    if isinstance(profiles, Mapping):
        payload = profiles.get(profile_id)
        if isinstance(payload, Mapping):
            return _coerce_mapping(payload)
    primary_id = snapshot.get("primary_profile_id")
    if isinstance(primary_id, str) and primary_id == profile_id:
        primary_profile = snapshot.get("primary_profile")
        if isinstance(primary_profile, Mapping):
            return _coerce_mapping(primary_profile)
    plant_id = snapshot.get("plant_id")
    if isinstance(plant_id, str) and plant_id == profile_id:
        primary_profile = snapshot.get("primary_profile")
        if isinstance(primary_profile, Mapping):
            return _coerce_mapping(primary_profile)
    return {}


def _resolve_profile_name(payload: Mapping[str, Any] | None, default: str | None = None) -> str:
    if isinstance(payload, Mapping):
        for key in ("name", "display_name", "plant_name"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        general = payload.get("general") if isinstance(payload.get("general"), Mapping) else None
        if isinstance(general, Mapping):
            value = general.get("display_name") or general.get("name")
            if isinstance(value, str) and value.strip():
                return value.strip()
    if isinstance(default, str) and default.strip():
        return default.strip()
    if isinstance(payload, Mapping):
        identifier = payload.get("profile_id") or payload.get("plant_id")
        if isinstance(identifier, str) and identifier.strip():
            return identifier.strip()
    return "Plant"


def _merge_sensor_lists(*maps: Mapping[str, Any] | None) -> dict[str, list[str]]:
    """Merge sensor mappings into a canonical list map."""

    merged: dict[str, list[str]] = {}
    for mapping in maps:
        if not isinstance(mapping, Mapping):
            continue
        for key, value in mapping.items():
            if isinstance(value, str):
                candidates: Sequence[str] = [value]
            elif isinstance(value, Sequence):
                candidates = [item for item in value if isinstance(item, str)]
            else:
                continue
            bucket = merged.setdefault(str(key), [])
            for item in candidates:
                if item and item not in bucket:
                    bucket.append(item)
    return merged


def _normalise_profile_sensors(payload: Mapping[str, Any] | None) -> dict[str, list[str]]:
    """Return the resolved sensor mapping for a profile payload."""

    if not isinstance(payload, Mapping):
        return {}

    sensors = _merge_sensor_lists(
        _normalise_sensor_map(payload.get("sensors")),
        _normalise_sensor_map((payload.get("general") or {}).get("sensors")),
    )

    # Preserve backwards-compatible aliases
    aliases = {
        "soil_moisture": "moisture",
        "light": "illuminance",
    }
    for alias, target in aliases.items():
        if alias in sensors and target not in sensors:
            sensors[target] = list(sensors[alias])

    return sensors


def _resolve_profile_thresholds(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    """Return threshold-style values for ``payload``."""

    if not isinstance(payload, Mapping):
        return {}

    thresholds = payload.get("thresholds")
    if isinstance(thresholds, Mapping) and thresholds:
        return _coerce_mapping(thresholds)

    resolved = payload.get("resolved_targets")
    computed: dict[str, Any] = {}
    if isinstance(resolved, Mapping):
        for key, value in resolved.items():
            if isinstance(value, Mapping) and "value" in value:
                computed[str(key)] = value["value"]
    if computed:
        return computed

    variables = payload.get("variables")
    if isinstance(variables, Mapping):
        for key, value in variables.items():
            if isinstance(value, Mapping) and "value" in value:
                computed[str(key)] = value["value"]
    return computed


def _build_profile_context(
    entry: ConfigEntry,
    snapshot: Mapping[str, Any],
    profile_id: str,
    payload: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Return merged profile metadata for quick lookups."""

    resolved_payload = _coerce_mapping(payload) or _profile_payload_from_snapshot(snapshot, profile_id)

    default_name = None
    if profile_id == snapshot.get("plant_id"):
        default_name = snapshot.get("plant_name")

    name = _resolve_profile_name(resolved_payload, default_name) or profile_id

    sensors = _normalise_profile_sensors(resolved_payload)
    if profile_id == snapshot.get("plant_id"):
        primary_sensors = _normalise_sensor_map(snapshot.get("sensors"))
        sensors = _merge_sensor_lists(primary_sensors, sensors)

    thresholds = _resolve_profile_thresholds(resolved_payload)
    if not thresholds and profile_id == snapshot.get("plant_id"):
        thresholds = _coerce_mapping(snapshot.get("thresholds"))

    context = {
        "id": profile_id,
        "name": name,
        "payload": resolved_payload,
        "sensors": sensors,
        "thresholds": thresholds,
    }

    general = resolved_payload.get("general")
    if isinstance(general, Mapping):
        image = general.get("image") or general.get("image_url")
        if isinstance(image, str) and image:
            context["image_url"] = image

    image_url = resolved_payload.get("image_url") or resolved_payload.get("image")
    if isinstance(image_url, str) and image_url:
        context.setdefault("image_url", image_url)

    return context


def build_entry_device_info(entry: ConfigEntry, snapshot: Mapping[str, Any] | None) -> dict[str, Any]:
    """Return a ``device_info`` style payload for the config entry."""

    identifier = entry_device_identifier(entry.entry_id)
    plant_name = None
    if isinstance(snapshot, Mapping):
        plant_name = snapshot.get("plant_name") or snapshot.get("primary_profile_name")
    name = plant_name or entry.title or f"Plant {str(entry.entry_id)[:6]}"

    info: dict[str, Any] = {
        "identifiers": {identifier},
        "manufacturer": "Horticulture Assistant",
        "model": "Horticulture Assistant",
        "name": name,
    }

    if isinstance(snapshot, Mapping):
        primary = snapshot.get("primary_profile")
        if isinstance(primary, Mapping):
            general = primary.get("general") if isinstance(primary.get("general"), Mapping) else None
            if isinstance(general, Mapping):
                area = general.get("area") or general.get("grow_area")
                if isinstance(area, str) and area.strip():
                    info["suggested_area"] = area.strip()
            model = primary.get("model") or primary.get("profile_type")
            if isinstance(model, str) and model.strip():
                info["model"] = model.strip()

    return info


def build_profile_device_info(
    entry_id: str | None,
    profile_id: str,
    payload: Mapping[str, Any] | None,
    snapshot: Mapping[str, Any] | None,
    *,
    default_name: str | None = None,
) -> dict[str, Any]:
    """Return a ``device_info`` style payload for a profile device."""

    resolved_payload = _coerce_mapping(payload)
    if not resolved_payload and isinstance(snapshot, Mapping):
        resolved_payload = _profile_payload_from_snapshot(snapshot, profile_id)

    name = _resolve_profile_name(resolved_payload, default_name) or profile_id
    identifier = profile_device_identifier(entry_id, profile_id)

    info: dict[str, Any] = {
        "identifiers": {identifier},
        "manufacturer": resolved_payload.get("manufacturer") or "Horticulture Assistant",
        "model": resolved_payload.get("model")
        or (resolved_payload.get("general", {}) or {}).get("plant_type")
        or "Plant Profile",
        "name": name,
    }

    if entry_id:
        info["via_device"] = entry_device_identifier(entry_id)

    general_section = resolved_payload.get("general")
    if isinstance(general_section, Mapping):
        area = general_section.get("area") or general_section.get("grow_area")
        if isinstance(area, str) and area.strip():
            info["suggested_area"] = area.strip()
        location = general_section.get("location") or general_section.get("zone")
        if isinstance(location, str) and location.strip():
            info.setdefault("suggested_area", location.strip())
        species = general_section.get("species") or resolved_payload.get("species_display")
        if isinstance(species, str) and species.strip():
            info["hw_version"] = species.strip()

    species_display = resolved_payload.get("species_display")
    if isinstance(species_display, str) and species_display.strip():
        info.setdefault("hw_version", species_display.strip())

    return info


def _coerce_device_identifiers(value: Any) -> set[tuple[str, str]]:
    identifiers: set[tuple[str, str]] = set()
    if isinstance(value, set):
        for item in value:
            if isinstance(item, tuple) and len(item) == 2:
                identifiers.add((str(item[0]), str(item[1])))
    elif isinstance(value, Mapping):
        for key, item in value.items():
            if isinstance(item, tuple) and len(item) == 2:
                identifiers.add((str(item[0]), str(item[1])))
            elif isinstance(key, str):
                identifiers.add((str(key), str(item)))
    elif isinstance(value, list | tuple):
        for item in value:
            if isinstance(item, tuple) and len(item) == 2:
                identifiers.add((str(item[0]), str(item[1])))
    return identifiers


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

    raw_profiles = snapshot.get("profiles")
    profile_payloads: Mapping[str, Any]
    if isinstance(raw_profiles, Mapping):
        profile_payloads = raw_profiles
    else:
        profile_payloads = {}

    new_profile_ids: set[str] = set()
    for pid in profile_payloads.keys():
        if isinstance(pid, str) and pid:
            new_profile_ids.add(pid)

    primary_id = snapshot.get("primary_profile_id")
    if isinstance(primary_id, str) and primary_id:
        new_profile_ids.add(primary_id)

    plant_identifier = snapshot["plant_id"]
    if isinstance(plant_identifier, str) and plant_identifier:
        new_profile_ids.add(plant_identifier)

    previous_profiles = set(entry_data.get("profile_ids", []))

    # Remove stale profile index mappings for this entry
    if previous_profiles:
        for stale_pid in previous_profiles - new_profile_ids:
            if by_pid.get(stale_pid) is entry_data:
                by_pid.pop(stale_pid, None)

    # Ensure lookups point at the refreshed entry data for every profile id
    for pid in new_profile_ids:
        by_pid[pid] = entry_data

    entry_data["profiles"] = dict(profile_payloads)
    entry_data["profile_ids"] = sorted(new_profile_ids)

    entry_device_info = _normalise_device_info(build_entry_device_info(entry, snapshot))
    identifiers = entry_device_info.get("identifiers") or {entry_device_identifier(entry.entry_id)}
    if not isinstance(identifiers, set):
        identifiers = _coerce_device_identifiers(identifiers)
    entry_device_info["identifiers"] = identifiers or {entry_device_identifier(entry.entry_id)}
    entry_data["entry_device_info"] = entry_device_info
    entry_data["entry_device_identifier"] = next(iter(entry_device_info["identifiers"]))

    profile_devices: dict[str, dict[str, Any]] = {}
    profile_contexts: dict[str, dict[str, Any]] = {}
    for pid in sorted(new_profile_ids):
        if not isinstance(pid, str) or not pid:
            continue
        payload = profile_payloads.get(pid)
        default_name = snapshot.get("plant_name") if pid == snapshot.get("plant_id") else None
        profile_info = _normalise_device_info(
            build_profile_device_info(
                entry.entry_id,
                pid,
                payload,
                snapshot,
                default_name=default_name,
            )
        )
        profile_devices[pid] = profile_info
        profile_contexts[pid] = _build_profile_context(entry, snapshot, pid, payload)
    entry_data["profile_devices"] = profile_devices
    entry_data["profile_contexts"] = profile_contexts

    async_sync_entry_devices(hass, entry, snapshot=snapshot)
    return entry_data


def async_sync_entry_devices(
    hass: HomeAssistant,
    entry: ConfigEntry,
    *,
    snapshot: dict[str, Any] | None = None,
) -> None:
    """Ensure device registry entries reflect the current profile layout."""

    try:
        device_registry = dr.async_get(hass)
    except Exception:  # pragma: no cover - defensive fallback
        return

    if device_registry is None:
        return

    snapshot = snapshot or build_entry_snapshot(entry)

    entry_info = _normalise_device_info(build_entry_device_info(entry, snapshot))
    entry_kwargs = _clean_device_kwargs(entry_info)
    identifiers = entry_kwargs.get("identifiers") or {entry_device_identifier(entry.entry_id)}
    if not isinstance(identifiers, set) or not identifiers:
        identifiers = _coerce_device_identifiers(identifiers) or {entry_device_identifier(entry.entry_id)}
    entry_kwargs["identifiers"] = identifiers
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        **entry_kwargs,
    )

    desired_identifiers = set(identifiers)
    profile_prefix = f"{entry.entry_id}:profile:"
    legacy_prefix = "profile:"

    raw_profiles = snapshot.get("profiles")
    profile_ids: set[str] = set()
    if isinstance(raw_profiles, Mapping):
        for pid in raw_profiles.keys():
            if isinstance(pid, str) and pid:
                profile_ids.add(pid)

    primary_candidates = (
        snapshot.get("primary_profile_id"),
        snapshot.get("plant_id"),
    )
    for candidate in primary_candidates:
        if isinstance(candidate, str) and candidate:
            profile_ids.add(candidate)

    for pid in sorted(profile_ids):
        payload = raw_profiles.get(pid) if isinstance(raw_profiles, Mapping) else None
        default_name = snapshot.get("plant_name") if pid == snapshot.get("plant_id") else None
        info = _normalise_device_info(
            build_profile_device_info(
                entry.entry_id,
                pid,
                payload,
                snapshot,
                default_name=default_name,
            )
        )
        kwargs = _clean_device_kwargs(info)
        identifiers = kwargs.get("identifiers") or {profile_device_identifier(entry.entry_id, pid)}
        if not isinstance(identifiers, set) or not identifiers:
            identifiers = _coerce_device_identifiers(identifiers) or {
                profile_device_identifier(entry.entry_id, pid)
            }
        kwargs["identifiers"] = identifiers
        desired_identifiers.update(identifiers)
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            **kwargs,
        )

    devices = getattr(device_registry, "devices", {})
    device_values = devices.values() if isinstance(devices, dict) else devices
    for device in list(device_values):
        if getattr(device, "config_entries", set()) and entry.entry_id not in device.config_entries:
            continue
        identifiers = getattr(device, "identifiers", set())
        prune = False
        for domain, ident in identifiers:
            if domain != DOMAIN:
                continue
            if (domain, ident) in desired_identifiers:
                break
            if ident.startswith(profile_prefix) or ident.startswith(legacy_prefix):
                prune = True
        if prune and hasattr(device_registry, "async_remove_device"):
            device_registry.async_remove_device(device.id)


def remove_entry_data(hass: HomeAssistant, entry_id: str) -> None:
    """Remove stored metadata for ``entry_id`` if present."""
    domain_data = hass.data.get(DOMAIN)
    if domain_data is not None:
        entry_data = domain_data.pop(entry_id, None)
        if entry_data:
            profile_ids = entry_data.get("profile_ids") or []
            plant_id = entry_data.get("plant_id")
            by_pid = domain_data.get(BY_PLANT_ID)
            if by_pid:
                if plant_id and by_pid.get(plant_id) is entry_data:
                    by_pid.pop(plant_id, None)
                for pid in profile_ids:
                    if pid == plant_id:
                        continue
                    if by_pid.get(pid) is entry_data:
                        by_pid.pop(pid, None)
        if not domain_data or (
            set(domain_data.keys()) <= {BY_PLANT_ID} and not domain_data.get(BY_PLANT_ID)
        ):
            hass.data.pop(DOMAIN, None)


def get_entry_data(hass: HomeAssistant, entry_or_id: ConfigEntry | str) -> dict | None:
    """Return stored entry metadata or ``None`` if missing."""
    entry_id = getattr(entry_or_id, "entry_id", entry_or_id)
    data = hass.data.get(DOMAIN, {})
    stored = data.get(entry_id)
    if stored is None:
        stored = data.get(BY_PLANT_ID, {}).get(entry_id)
    return stored


def get_entry_data_by_plant_id(hass: HomeAssistant, plant_id: str) -> dict | None:
    """Return stored entry metadata looked up by ``plant_id``."""
    return hass.data.get(DOMAIN, {}).get(BY_PLANT_ID, {}).get(plant_id)


def serialise_device_info(info: Mapping[str, Any] | None) -> dict[str, Any]:
    """Return a JSON-friendly representation of ``info``."""

    payload: dict[str, Any] = {}
    if not info:
        return payload

    normalised = _normalise_device_info(info)
    for key, value in normalised.items():
        if key in {"identifiers", "connections"}:
            if isinstance(value, set):
                payload[key] = _serialise_identifier_set(value)
            else:
                payload[key] = value
            continue

        if key == "via_device" and isinstance(value, tuple | list) and len(value) == 2:
            payload[key] = {"domain": str(value[0]), "id": str(value[1])}
            continue

        payload[key] = value

    return {k: v for k, v in payload.items() if v not in (None, "", [], {}, set())}


def resolve_entry_device_info(hass: HomeAssistant, entry_id: str | None) -> dict[str, Any] | None:
    """Return the device info payload for a config entry if available."""

    if not entry_id:
        return None

    stored = get_entry_data(hass, entry_id)
    if stored is None:
        return None

    info = stored.get("entry_device_info")
    if isinstance(info, Mapping):
        return _clean_device_kwargs(_normalise_device_info(info))

    entry = stored.get("config_entry")
    snapshot = stored.get("snapshot") if isinstance(stored.get("snapshot"), Mapping) else None
    if entry is not None:
        return _clean_device_kwargs(
            _normalise_device_info(build_entry_device_info(entry, snapshot))
        )
    return None


def resolve_profile_device_info(
    hass: HomeAssistant,
    entry_id: str | None,
    profile_id: str,
) -> dict[str, Any] | None:
    """Return device info for ``profile_id`` attached to ``entry_id``."""

    if not profile_id:
        return None

    stored = None
    if entry_id:
        stored = get_entry_data(hass, entry_id)
    if stored is None:
        stored = get_entry_data_by_plant_id(hass, profile_id)
    if stored is None:
        return None

    profile_devices = stored.get("profile_devices")
    if isinstance(profile_devices, Mapping):
        payload = profile_devices.get(profile_id)
        if isinstance(payload, Mapping):
            return _clean_device_kwargs(_normalise_device_info(payload))

    snapshot = stored.get("snapshot") if isinstance(stored.get("snapshot"), Mapping) else None
    entry = stored.get("config_entry") if stored else None
    entry_id = getattr(entry, "entry_id", entry_id)
    if entry is None:
        return None

    return _clean_device_kwargs(
        _normalise_device_info(
            build_profile_device_info(
                entry_id,
                profile_id,
                None,
                snapshot,
                default_name=stored.get("plant_name"),
            )
        )
    )


def resolve_profile_image_url(
    hass: HomeAssistant,
    entry_id: str | None,
    profile_id: str | None,
) -> str | None:
    """Return a best-effort image URL for the requested profile."""

    if hass is None:
        return None

    stored: dict | None = None
    if entry_id:
        stored = get_entry_data(hass, entry_id)
    if stored is None and profile_id:
        stored = get_entry_data_by_plant_id(hass, profile_id)
    if not stored:
        return None

    snapshot = stored.get("snapshot")
    if isinstance(snapshot, Mapping):
        profiles = snapshot.get("profiles")
        if isinstance(profiles, Mapping) and profile_id:
            profile = profiles.get(profile_id)
            if isinstance(profile, Mapping):
                for key in ("image_url", "image", "picture"):
                    value = profile.get(key)
                    if isinstance(value, str) and value.strip():
                        return value
        primary_id = snapshot.get("primary_profile_id")
        if primary_id and profile_id and primary_id == profile_id:
            primary_profile = snapshot.get("primary_profile")
            if isinstance(primary_profile, Mapping):
                for key in ("image_url", "image", "picture"):
                    value = primary_profile.get(key)
                    if isinstance(value, str) and value.strip():
                        return value

    entry = stored.get("config_entry")
    if entry is None:
        return None
    image_url = entry.options.get("image_url")
    if isinstance(image_url, str) and image_url:
        return image_url
    return None


def _build_profile_context_from_payload(
    hass: HomeAssistant,
    entry: ConfigEntry,
    stored: Mapping[str, Any],
    profile_id: str,
    context_payload: Mapping[str, Any] | None,
) -> ProfileContext:
    """Return a runtime context derived from stored metadata."""

    context = context_payload if isinstance(context_payload, Mapping) else {}
    snapshot = stored.get("snapshot") if isinstance(stored.get("snapshot"), Mapping) else None
    payload = context.get("payload")
    if not isinstance(payload, Mapping):
        payload = _profile_payload_from_snapshot(snapshot, profile_id)

    name = context.get("name")
    if not isinstance(name, str) or not name:
        name = _resolve_profile_name(payload, stored.get("plant_name")) or profile_id

    image_url = context.get("image_url")
    if not isinstance(image_url, str) or not image_url:
        image_url = resolve_profile_image_url(hass, entry.entry_id, profile_id)

    devices = stored.get("profile_devices") if isinstance(stored.get("profile_devices"), Mapping) else None
    device_payload = None
    if isinstance(devices, Mapping):
        candidate = devices.get(profile_id)
        if isinstance(candidate, Mapping):
            device_payload = candidate
    if device_payload is None:
        device_payload = build_profile_device_info(
            entry.entry_id,
            profile_id,
            payload,
            snapshot,
            default_name=name,
        )

    sensors = context.get("sensors")
    if not isinstance(sensors, Mapping):
        sensors = _normalise_profile_sensors(payload)

    thresholds = context.get("thresholds")
    if not isinstance(thresholds, Mapping):
        thresholds = _resolve_profile_thresholds(payload)

    return ProfileContext(
        id=profile_id,
        name=name,
        sensors=sensors,
        thresholds=thresholds,
        payload=payload,
        device_info=device_payload,
        image_url=image_url,
    )


def _fallback_profile_contexts(
    hass: HomeAssistant,
    entry: ConfigEntry,
    stored: Mapping[str, Any],
) -> dict[str, ProfileContext]:
    """Return a minimal context mapping when no stored metadata exists."""

    plant_id, plant_name = get_entry_plant_info(entry)
    snapshot = stored.get("snapshot") if isinstance(stored.get("snapshot"), Mapping) else None
    payload = _profile_payload_from_snapshot(snapshot, plant_id)

    sensors = get_primary_profile_sensors(entry)
    thresholds = get_primary_profile_thresholds(entry)

    image_url = resolve_profile_image_url(hass, entry.entry_id, plant_id)

    device_payload = build_profile_device_info(
        entry.entry_id,
        plant_id,
        payload,
        snapshot,
        default_name=plant_name,
    )

    context = ProfileContext(
        id=plant_id,
        name=plant_name,
        sensors=sensors,
        thresholds=thresholds,
        payload=payload,
        device_info=device_payload,
        image_url=image_url,
    )
    return {plant_id: context}


def resolve_profile_context_collection(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> ProfileContextCollection:
    """Return an aggregated view of stored profile contexts for ``entry``."""

    stored = get_entry_data(hass, entry)
    if stored is None:
        stored = store_entry_data(hass, entry)
    if stored is None:
        stored = {}

    raw_contexts = stored.get("profile_contexts") if isinstance(stored, Mapping) else None
    contexts: dict[str, ProfileContext] = {}
    if isinstance(raw_contexts, Mapping):
        for profile_id, payload in raw_contexts.items():
            if not isinstance(profile_id, str) or not profile_id:
                continue
            contexts[profile_id] = _build_profile_context_from_payload(
                hass,
                entry,
                stored,
                profile_id,
                payload if isinstance(payload, Mapping) else {},
            )

    if not contexts:
        contexts = _fallback_profile_contexts(hass, entry, stored)

    plant_id = stored.get("plant_id") if isinstance(stored, Mapping) else None
    plant_name = stored.get("plant_name") if isinstance(stored, Mapping) else None
    primary_id = stored.get("primary_profile_id") if isinstance(stored, Mapping) else None

    if not isinstance(primary_id, str) or not primary_id:
        primary_id = plant_id
    if (not isinstance(primary_id, str) or primary_id not in contexts) and contexts:
        primary_id = next(iter(contexts))

    primary = contexts.get(primary_id) if primary_id else None
    if primary is not None:
        plant_name = plant_name or primary.name
        plant_id = plant_id or primary.id

    if not isinstance(plant_id, str) or not plant_id:
        plant_id, fallback_name = get_entry_plant_info(entry)
        plant_name = plant_name or fallback_name

    if not isinstance(plant_name, str) or not plant_name:
        plant_name = entry.title or plant_id or entry.entry_id

    if not isinstance(primary_id, str) or not primary_id:
        primary_id = plant_id

    return ProfileContextCollection(
        entry=entry,
        stored=stored,
        contexts=contexts,
        plant_id=plant_id,
        plant_name=plant_name,
        primary_id=primary_id,
    )
