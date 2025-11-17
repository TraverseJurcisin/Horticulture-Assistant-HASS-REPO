"""Helpers for working with integration config entries."""

from __future__ import annotations

import inspect
import types
from collections.abc import Iterable, Iterator, Mapping, Sequence, Set
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any

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

        async def async_get_or_create(self, **_kwargs):
            return types.SimpleNamespace(id="stub")

        async def async_remove_device(self, *_args, **_kwargs):
            return None

        async def async_get_device(self, *_args, **_kwargs):  # pragma: no cover - basic stub
            return None

    dr = types.SimpleNamespace(async_get=lambda _hass: _DeviceRegistryStub())  # type: ignore[assignment]

try:  # pragma: no cover - allow running tests without Home Assistant
    from homeassistant.helpers.dispatcher import async_dispatcher_send
except (ModuleNotFoundError, ImportError):  # pragma: no cover - executed in stubbed env

    def async_dispatcher_send(*_args, **_kwargs) -> None:
        """Stubbed dispatcher used when Home Assistant is unavailable."""

        return None


from ..const import (
    CONF_PLANT_ID,
    CONF_PLANT_NAME,
    CONF_PROFILES,
    DOMAIN,
    signal_profile_contexts_updated,
)

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
            cleaned = raw.strip()
            items = (cleaned,) if cleaned else ()
        elif isinstance(raw, Set):
            cleaned: list[str] = []
            for item in raw:
                if not isinstance(item, str):
                    continue
                trimmed = item.strip()
                if trimmed:
                    cleaned.append(trimmed)
            items = tuple(sorted(dict.fromkeys(cleaned), key=str.casefold))
        elif isinstance(raw, Sequence):
            cleaned: list[str] = []
            seen: set[str] = set()
            for item in raw:
                if not isinstance(item, str):
                    continue
                trimmed = item.strip()
                if trimmed and trimmed not in seen:
                    cleaned.append(trimmed)
                    seen.add(trimmed)
            items = tuple(cleaned)
        else:
            items = ()
        if items:
            sensors[key] = items
    return sensors


def _normalise_metric_mappings(
    value: Mapping[str, Any] | None,
) -> dict[str, Mapping[str, Any]]:
    """Return a read-only mapping for metric metadata buckets."""

    metrics: dict[str, Mapping[str, Any]] = {}
    if not isinstance(value, Mapping):
        return metrics

    for category, bucket in value.items():
        if not isinstance(category, str) or not category:
            continue
        if not isinstance(bucket, Mapping):
            continue
        cleaned: dict[str, Mapping[str, Any]] = {}
        for key, meta in bucket.items():
            if not isinstance(key, str) or not key:
                continue
            if isinstance(meta, Mapping):
                cleaned[key] = MappingProxyType(dict(meta))
            else:
                cleaned[key] = MappingProxyType({"value": meta})
        metrics[category] = MappingProxyType(cleaned)
    return metrics


@dataclass(frozen=True, slots=True)
class ProfileContext:
    """Runtime metadata describing a plant profile and its device."""

    id: str
    name: str
    sensors: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    thresholds: Mapping[str, Any] = field(default_factory=dict)
    metrics: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)
    payload: Mapping[str, Any] = field(default_factory=dict)
    device_info: Mapping[str, Any] = field(default_factory=dict)
    image_url: str | None = None

    def __post_init__(self) -> None:  # pragma: no cover - exercised indirectly
        sensors = _normalise_sensor_sequences(self.sensors)
        thresholds = _coerce_mapping(self.thresholds)
        metrics = _normalise_metric_mappings(self.metrics)
        payload = _coerce_mapping(self.payload)
        device = _clean_device_kwargs(_normalise_device_info(self.device_info))
        object.__setattr__(self, "sensors", MappingProxyType(sensors))
        object.__setattr__(self, "thresholds", MappingProxyType(thresholds))
        object.__setattr__(self, "metrics", MappingProxyType(metrics))
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
        return any(self.sensors.get(role) for role in roles)

    def has_all_sensors(self, *roles: str) -> bool:
        """Return ``True`` when every ``role`` has at least one entity id."""

        if not roles:
            return bool(self.sensors)
        return all(self.sensors.get(role) for role in roles)

    def get_threshold(self, key: str, default: Any | None = None) -> Any | None:
        """Return a stored threshold value for ``key`` if available."""

        return self.thresholds.get(key, default)

    def metrics_for(self, category: str) -> Mapping[str, Any]:
        """Return the metrics bucket stored for ``category``."""

        bucket = self.metrics.get(category)
        if isinstance(bucket, Mapping):
            return bucket
        return MappingProxyType({})

    def metric(self, category: str, key: str) -> Mapping[str, Any] | None:
        """Return metric metadata for ``category``/``key`` if present."""

        bucket = self.metrics_for(category)
        metric = bucket.get(key)
        return metric if isinstance(metric, Mapping) else None

    def metric_value(self, category: str, key: str, default: Any | None = None) -> Any | None:
        """Return the scalar value for ``category``/``key`` if present."""

        metric = self.metric(category, key)
        if isinstance(metric, Mapping):
            value = metric.get("value")
            return metric.get("value", default) if value is not None else default
        return default

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


def _coerce_device_registry_entry(result: Any) -> tuple[Any | None, str | None]:
    """Return ``result`` normalised into ``(device, id)`` pair."""

    def _candidate_from_mapping(payload: Mapping[str, Any]) -> Any | None:
        for key in ("device", "entry", "result"):
            if key in payload:
                return payload[key]
        return None

    device = result

    if isinstance(result, Mapping):
        nested = _candidate_from_mapping(result)
        if nested is not None and nested is not result:
            nested_device, nested_id = _coerce_device_registry_entry(nested)
            if nested_device is not None and nested_id:
                return nested_device, nested_id
        device = result

    if isinstance(result, list | tuple):
        for item in result:
            candidate_device, candidate_id = _coerce_device_registry_entry(item)
            if candidate_device is not None and candidate_id:
                return candidate_device, candidate_id
        device = result[0] if result else None

    if device is None:
        return None, None

    device_id = getattr(device, "id", None)
    if device_id is None and isinstance(device, Mapping):
        device_id = device.get("id")

    if isinstance(device_id, str):
        text = device_id.strip()
        device_id = text or None
    elif device_id is not None:
        try:
            text = str(device_id).strip()
        except Exception:  # pragma: no cover - defensive conversion
            device_id = None
        else:
            device_id = text or None

    return device, device_id


async def _async_resolve_device_registry(
    hass: HomeAssistant,
    device_registry: Any | None = None,
) -> Any | None:
    """Return a loaded device registry instance if available."""

    if device_registry is not None:
        return device_registry

    async def _try_getter(name: str) -> Any | None:
        getter = getattr(dr, name, None)
        if not callable(getter):
            return None
        try:
            result = getter(hass)
        except Exception:
            return None
        if inspect.isawaitable(result):
            try:
                result = await result
            except Exception:
                return None
        return result

    getter_names = (
        "async_get",
        "async_get_registry",
        "async_get_device_registry",
    )

    for getter_name in getter_names:
        registry = await _try_getter(getter_name)
        if registry is not None:
            return registry

    async def _run_loader(name: str) -> Any | None:
        loader = getattr(dr, name, None)
        if not callable(loader):
            return None
        try:
            result = loader(hass)
        except Exception:
            return None
        if inspect.isawaitable(result):
            try:
                result = await result
            except Exception:
                return None
        return result

    loader_names = (
        "async_load",
        "async_load_registry",
        "async_load_device_registry",
    )

    for loader_name in loader_names:
        load_result = await _run_loader(loader_name)
        if load_result is not None and hasattr(load_result, "async_get_or_create"):
            return load_result
        for getter_name in getter_names:
            registry = await _try_getter(getter_name)
            if registry is not None:
                return registry

    return None


async def _async_device_registry_get_or_create(
    device_registry: Any,
    entry: ConfigEntry,
    kwargs: Mapping[str, Any],
    entry_identifier: tuple[str, str],
    entry_device_id: str | None,
):
    """Call ``async_get_or_create`` with compatibility for via-device kwargs."""

    base_payload = dict(kwargs)

    def _coerce_device_id(value: Any) -> str | None:
        if value is None:
            return None
        if isinstance(value, str):
            text = value.strip()
            return text or None
        try:
            text = str(value)
        except Exception:  # pragma: no cover - defensive conversion
            return None
        text = text.strip()
        return text or None

    resolved_entry_device_id = _coerce_device_id(entry_device_id)

    if not resolved_entry_device_id:
        lookup = getattr(device_registry, "async_get_device", None)
        if callable(lookup):
            try:
                maybe_device = lookup({entry_identifier})
            except TypeError:  # pragma: no cover - mismatched signature
                maybe_device = None
            else:
                if inspect.isawaitable(maybe_device):
                    maybe_device = await maybe_device
            if maybe_device is not None:
                candidate = getattr(maybe_device, "id", None)
                if candidate is None and isinstance(maybe_device, Mapping):
                    candidate = maybe_device.get("id")
                resolved_entry_device_id = _coerce_device_id(candidate)

    attempts: list[dict[str, Any]] = []

    def _queue(payload: dict[str, Any]) -> None:
        for existing in attempts:
            if existing == payload:
                return
        attempts.append(payload)

    if resolved_entry_device_id:
        payload = dict(base_payload)
        payload["via_device_id"] = resolved_entry_device_id
        if entry_identifier:
            payload["via_device"] = entry_identifier
        _queue(payload)

        payload = dict(base_payload)
        payload["via_device_id"] = resolved_entry_device_id
        payload.pop("via_device", None)
        _queue(payload)

    _queue(dict(base_payload))

    payload = dict(base_payload)
    payload.pop("via_device_id", None)
    payload.pop("via_device", None)
    _queue(payload)

    last_error: Exception | None = None

    for payload in attempts:
        try:
            result = device_registry.async_get_or_create(
                config_entry_id=entry.entry_id,
                **payload,
            )
            if inspect.isawaitable(result):
                result = await result
            return result
        except (TypeError, ValueError) as err:
            last_error = err
            continue

    if last_error is not None:
        raise last_error

    result = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        **base_payload,
    )
    if inspect.isawaitable(result):
        result = await result
    return result


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
                cleaned = item.strip()
                if cleaned and cleaned not in bucket:
                    bucket.append(cleaned)
    return merged


def _normalise_profile_sensors(payload: Mapping[str, Any] | None) -> dict[str, list[str]]:
    """Return the resolved sensor mapping for a profile payload."""

    if not isinstance(payload, Mapping):
        return {}

    sensors = _merge_sensor_lists(
        _coerce_mapping(payload.get("sensors")),
        _coerce_mapping((payload.get("general") or {}).get("sensors")),
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


def _extract_scalar_value(source: Any) -> Any | None:
    """Return a scalar numeric/string value from nested payloads."""

    if source is None:
        return None
    if isinstance(source, Mapping):
        for key in ("value", "current", "current_value", "target"):
            if key in source:
                resolved = _extract_scalar_value(source[key])
                if resolved is not None:
                    return resolved
        return None
    return source


def _resolve_profile_thresholds(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    """Return threshold-style values for ``payload``."""

    if not isinstance(payload, Mapping):
        return {}

    thresholds = payload.get("thresholds")
    if isinstance(thresholds, Mapping) and thresholds:
        return _coerce_mapping(thresholds)

    computed: dict[str, Any] = {}

    resolved = payload.get("resolved_targets")
    if isinstance(resolved, Mapping):
        for key, value in resolved.items():
            scalar = _extract_scalar_value(value)
            if scalar is not None:
                computed[str(key)] = scalar

    targets = payload.get("targets")
    if isinstance(targets, Mapping):
        for key, value in targets.items():
            if str(key) in computed:
                continue
            scalar = _extract_scalar_value(value)
            if scalar is not None:
                computed[str(key)] = scalar

    variables = payload.get("variables")
    if isinstance(variables, Mapping):
        for key, value in variables.items():
            if str(key) in computed:
                continue
            scalar = _extract_scalar_value(value)
            if scalar is not None:
                computed[str(key)] = scalar

    return computed


def _extract_metric_unit(source: Any) -> str | None:
    """Return a textual unit from ``source`` when present."""

    if isinstance(source, Mapping):
        for key in ("unit", "units", "unit_of_measurement", "uom"):
            unit = source.get(key)
            if isinstance(unit, str) and unit.strip():
                return unit.strip()
    return None


_RANGE_SUFFIXES = {
    "min": "min",
    "minimum": "min",
    "lower": "min",
    "low": "min",
    "max": "max",
    "maximum": "max",
    "upper": "max",
    "high": "max",
}


def _populate_metric_range_entries(
    bucket: dict[str, Any],
    base_key: str,
    value: Any,
) -> None:
    """Expand range-style mappings into discrete metric entries."""

    if not isinstance(value, Mapping):
        return

    base_unit = _extract_metric_unit(value)

    for raw_key, raw_value in value.items():
        suffix = _RANGE_SUFFIXES.get(str(raw_key).lower())
        if not suffix:
            continue
        scalar = _extract_scalar_value(raw_value)
        if scalar is None:
            continue
        metric_key = f"{base_key}_{suffix}"
        if not metric_key or metric_key in bucket:
            continue
        meta: dict[str, Any] = {"value": scalar}
        unit = _extract_metric_unit(raw_value) or base_unit
        if unit:
            meta["unit"] = unit
        if isinstance(raw_value, Mapping):
            meta["raw"] = _coerce_mapping(raw_value)
        elif isinstance(value, Mapping):
            meta["raw"] = _coerce_mapping({raw_key: raw_value})
        bucket[metric_key] = meta


def _resolve_profile_metrics(
    payload: Mapping[str, Any] | None,
    *,
    thresholds: Mapping[str, Any] | None = None,
) -> dict[str, dict[str, Any]]:
    """Return structured metric metadata for profile payloads."""

    metrics: dict[str, dict[str, Any]] = {}

    def _collect(
        category: str,
        mapping: Mapping[str, Any] | None,
    ) -> None:
        if not isinstance(mapping, Mapping):
            return
        bucket: dict[str, Any] = {}
        for key, value in mapping.items():
            if not isinstance(key, str) or not key:
                continue
            scalar = _extract_scalar_value(value)
            if scalar is None:
                _populate_metric_range_entries(bucket, str(key), value)
                continue
            meta: dict[str, Any] = {"value": scalar}
            unit = _extract_metric_unit(value)
            if unit:
                meta["unit"] = unit
            if isinstance(value, Mapping):
                meta["raw"] = _coerce_mapping(value)
            bucket[str(key)] = meta
            _populate_metric_range_entries(bucket, str(key), value)
        if bucket:
            metrics[category] = bucket

    if isinstance(thresholds, Mapping) and thresholds:
        bucket: dict[str, Any] = {}
        for key, value in thresholds.items():
            if not isinstance(key, str) or not key:
                continue
            bucket[key] = {"value": value}
        if bucket:
            metrics["thresholds"] = bucket

    if isinstance(payload, Mapping):
        _collect("resolved_targets", payload.get("resolved_targets"))
        _collect("targets", payload.get("targets"))
        _collect("variables", payload.get("variables"))

    return metrics


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

    metrics = _resolve_profile_metrics(resolved_payload, thresholds=thresholds)
    if profile_id == snapshot.get("plant_id") and "thresholds" not in metrics:
        snapshot_thresholds = _coerce_mapping(snapshot.get("thresholds"))
        if snapshot_thresholds:
            metrics.setdefault("thresholds", {})
            for key, value in snapshot_thresholds.items():
                metrics["thresholds"].setdefault(str(key), {"value": value})

    context = {
        "id": profile_id,
        "name": name,
        "payload": resolved_payload,
        "sensors": sensors,
        "thresholds": thresholds,
        "metrics": metrics,
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


def _normalise_profile_identifier(value: Any) -> str:
    """Return ``value`` coerced into a canonical profile identifier."""

    if isinstance(value, str):
        return value.strip()
    if value is None:
        return ""
    return str(value).strip()


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

    raw_general = resolved_payload.get("general")
    general_section = raw_general if isinstance(raw_general, Mapping) else None
    plant_type = general_section.get("plant_type") if general_section is not None else None

    info: dict[str, Any] = {
        "identifiers": {identifier},
        "manufacturer": resolved_payload.get("manufacturer") or "Horticulture Assistant",
        "model": resolved_payload.get("model") or plant_type or "Plant Profile",
        "name": name,
    }

    if entry_id:
        info["via_device"] = entry_device_identifier(entry_id)

    if general_section is not None:
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


def _as_identifier_pair(item: Any) -> tuple[str, str] | None:
    """Return ``item`` coerced into an identifier pair if possible."""

    if isinstance(item, tuple) and len(item) == 2:
        return str(item[0]), str(item[1])

    if isinstance(item, Mapping):
        lookup = {str(key).lower(): value for key, value in item.items()}

        def _candidate(*names: str) -> Any | None:
            for name in names:
                if name in lookup:
                    return lookup[name]
            return None

        domain = _candidate("domain", "type", "namespace", "key")
        identifier = _candidate("id", "identifier", "value")
        if domain is None and identifier is None and len(item) == 2:
            first, second = list(item.values())
            return str(first), str(second)
        if domain is not None and identifier is not None:
            return str(domain), str(identifier)
        for key in ("0", 0):
            if key in item:
                domain = item[key]
                break
        else:
            domain = None
        for key in ("1", 1):
            if key in item:
                identifier = item[key]
                break
        if domain is not None and identifier is not None:
            return str(domain), str(identifier)
        return None

    if isinstance(item, Sequence) and not isinstance(item, str | bytes):
        if len(item) != 2:
            return None
        first, second = item[0], item[1]
        return str(first), str(second)
    return None


def _coerce_device_identifiers(value: Any) -> set[tuple[str, str]]:
    identifiers: set[tuple[str, str]] = set()
    direct_pair = _as_identifier_pair(value)

    if isinstance(value, Set):
        for item in value:
            if pair := _as_identifier_pair(item):
                identifiers.add(pair)
        if identifiers:
            return identifiers
    elif isinstance(value, Mapping):
        if direct_pair:
            key_set = {str(key).lower() for key in value}
            valid_keys = {
                "domain",
                "id",
                "identifier",
                "value",
                "type",
                "namespace",
                "key",
                "0",
                "1",
            }
            if key_set and key_set <= valid_keys:
                identifiers.add(direct_pair)
                return identifiers
        for key, item in value.items():
            if pair := _as_identifier_pair(item):
                identifiers.add(pair)
                continue
            if isinstance(item, Mapping):
                candidate = None
                for name in ("id", "identifier", "value"):
                    if name in item:
                        candidate = item[name]
                        break
                if candidate is None and len(item) == 1:
                    candidate = next(iter(item.values()))
                item = candidate
            if item is None:
                continue
            domain = key.strip() if isinstance(key, str) else str(key).strip()
            if not domain:
                continue
            identifier = item.strip() if isinstance(item, str) else str(item).strip()
            if not identifier:
                continue
            identifiers.add((domain, identifier))
        if identifiers:
            return identifiers
    elif isinstance(value, Sequence) and not isinstance(value, str | bytes):
        for item in value:
            if pair := _as_identifier_pair(item):
                identifiers.add(pair)
        if identifiers:
            return identifiers

    if direct_pair:
        identifiers.add(direct_pair)
    return identifiers


def get_entry_plant_info(entry: ConfigEntry) -> tuple[str, str]:
    """Return ``(plant_id, plant_name)`` for a config entry."""

    primary_id = get_primary_profile_id(entry)
    raw_identifier = primary_id or entry.data.get(CONF_PLANT_ID) or entry.entry_id
    plant_id = _normalise_profile_identifier(raw_identifier) or str(entry.entry_id)

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
        items: Sequence[str]
        if isinstance(item, str):
            items = [item]
        elif isinstance(item, Sequence) and not isinstance(item, str | bytes):
            items = [cand for cand in item if isinstance(cand, str)]
        else:
            continue
        for candidate in items:
            cleaned = candidate.strip()
            if cleaned:
                sensors[str(key)] = cleaned
                break
    return sensors


def get_primary_profile_id(entry: ConfigEntry) -> str | None:
    """Return the profile id most closely associated with ``entry``."""

    candidates: tuple[Any, ...] = (
        entry.data.get(CONF_PLANT_ID),
        entry.options.get(CONF_PLANT_ID) if isinstance(entry.options, Mapping) else None,
    )

    for candidate in candidates:
        canonical = _normalise_profile_identifier(candidate)
        if canonical:
            return canonical

    profiles = entry.options.get(CONF_PROFILES)
    if isinstance(profiles, Mapping):
        for key, value in profiles.items():
            if not isinstance(key, str) or not isinstance(value, Mapping):
                continue
            canonical = _normalise_profile_identifier(key)
            if canonical:
                return canonical

    return None


def get_primary_profile_options(entry: ConfigEntry) -> dict[str, Any]:
    """Return the options payload for the primary profile if available."""

    profiles = entry.options.get(CONF_PROFILES)
    if not isinstance(profiles, Mapping):
        return {}

    plant_id = get_primary_profile_id(entry)
    if plant_id:
        canonical = _normalise_profile_identifier(plant_id)
        for key, payload in profiles.items():
            if not isinstance(payload, Mapping):
                continue
            if _normalise_profile_identifier(key) == canonical and canonical:
                return _coerce_mapping(payload)

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
            canonical_pid = _normalise_profile_identifier(pid)
            if not canonical_pid:
                continue
            if isinstance(payload, Mapping):
                existing = profiles.setdefault(canonical_pid, {})
                existing.update(_coerce_mapping(payload))
            else:
                profiles.setdefault(canonical_pid, {})

    canonical_primary = _normalise_profile_identifier(primary_id) or plant_id

    return {
        "plant_id": plant_id,
        "plant_name": plant_name,
        "primary_profile_id": canonical_primary,
        "primary_profile_name": plant_name,
        "primary_profile": primary_profile,
        "profiles": profiles,
        "sensors": sensors,
        "thresholds": thresholds,
    }


async def store_entry_data(hass: HomeAssistant, entry: ConfigEntry) -> dict:
    """Store entry metadata under ``hass.data`` and return it."""
    data = hass.data.setdefault(DOMAIN, {})
    by_pid = data.setdefault(BY_PLANT_ID, {})
    entry_data: dict[str, Any] = {"config_entry": entry}
    data[entry.entry_id] = entry_data
    return await update_entry_data(hass, entry, entry_data=entry_data, by_pid=by_pid)


async def update_entry_data(
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

    entry_data.get("plant_id")
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
    profile_payloads: dict[str, Mapping[str, Any]] = {}
    if isinstance(raw_profiles, Mapping):
        for pid, payload in raw_profiles.items():
            canonical_pid = _normalise_profile_identifier(pid)
            if not canonical_pid:
                continue
            if isinstance(payload, Mapping):
                profile_payloads[canonical_pid] = _coerce_mapping(payload)
            else:
                profile_payloads.setdefault(canonical_pid, {})

    new_profile_ids: set[str] = set(profile_payloads.keys())

    primary_id = _normalise_profile_identifier(snapshot.get("primary_profile_id"))
    if primary_id:
        new_profile_ids.add(primary_id)

    plant_identifier = _normalise_profile_identifier(snapshot["plant_id"])
    if plant_identifier:
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
    entry_identifier = entry_device_identifier(entry.entry_id)
    identifiers = entry_device_info.get("identifiers") or {entry_identifier}
    if not isinstance(identifiers, set):
        identifiers = _coerce_device_identifiers(identifiers)
    entry_device_info["identifiers"] = identifiers or {entry_identifier}
    entry_data["entry_device_info"] = entry_device_info
    entry_data["entry_device_identifier"] = entry_identifier

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

    await async_sync_entry_devices(hass, entry, snapshot=snapshot)
    return entry_data


async def async_sync_entry_devices(
    hass: HomeAssistant,
    entry: ConfigEntry,
    *,
    snapshot: dict[str, Any] | None = None,
) -> None:
    """Ensure device registry entries reflect the current profile layout."""

    device_registry = await _async_resolve_device_registry(hass)

    if device_registry is None:
        return

    snapshot = snapshot or build_entry_snapshot(entry)

    entry_info = _normalise_device_info(build_entry_device_info(entry, snapshot))
    entry_kwargs = _clean_device_kwargs(entry_info)
    entry_identifier = entry_device_identifier(entry.entry_id)
    identifiers = entry_kwargs.get("identifiers") or {entry_identifier}
    if not isinstance(identifiers, set) or not identifiers:
        identifiers = _coerce_device_identifiers(identifiers) or {entry_identifier}
    if entry_identifier not in identifiers:
        identifiers.add(entry_identifier)
    entry_kwargs["identifiers"] = identifiers
    entry_device_result = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        **entry_kwargs,
    )
    if inspect.isawaitable(entry_device_result):
        entry_device_result = await entry_device_result

    _entry_device, entry_device_id = _coerce_device_registry_entry(entry_device_result)

    desired_identifiers = set(identifiers)
    profile_prefix = f"{entry.entry_id}:profile:"
    legacy_prefix = "profile:"

    raw_profiles = snapshot.get("profiles")
    canonical_profiles: dict[str, Mapping[str, Any]] = {}
    if isinstance(raw_profiles, Mapping):
        for pid, payload in raw_profiles.items():
            canonical_pid = _normalise_profile_identifier(pid)
            if not canonical_pid:
                continue
            if isinstance(payload, Mapping):
                canonical_profiles[canonical_pid] = _coerce_mapping(payload)
            else:
                canonical_profiles.setdefault(canonical_pid, {})

    snapshot_primary_id = _normalise_profile_identifier(snapshot.get("primary_profile_id"))
    snapshot_plant_id = _normalise_profile_identifier(snapshot.get("plant_id"))

    profile_ids: set[str] = set(canonical_profiles.keys())
    for candidate in (snapshot_primary_id, snapshot_plant_id):
        if candidate:
            profile_ids.add(candidate)
            canonical_profiles.setdefault(candidate, {})

    for pid in sorted(profile_ids):
        payload = canonical_profiles.get(pid)
        default_name = snapshot.get("plant_name") if pid == snapshot_plant_id else None
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
        profile_identifier = profile_device_identifier(entry.entry_id, pid)
        identifiers = kwargs.get("identifiers") or {profile_identifier}
        if not isinstance(identifiers, set) or not identifiers:
            identifiers = _coerce_device_identifiers(identifiers) or {profile_identifier}
        if profile_identifier not in identifiers:
            identifiers.add(profile_identifier)
        kwargs["identifiers"] = identifiers
        desired_identifiers.update(identifiers)
        await _async_device_registry_get_or_create(
            device_registry,
            entry,
            kwargs,
            entry_identifier,
            entry_device_id,
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
            await device_registry.async_remove_device(device.id)


async def ensure_profile_device_registered(
    hass: HomeAssistant,
    entry: ConfigEntry,
    profile_id: str,
    profile_payload: Mapping[str, Any] | None,
    *,
    snapshot: Mapping[str, Any] | None = None,
    device_registry: Any | None = None,
) -> None:
    """Create the device for ``profile_id`` when it's missing from registry sync."""

    device_registry = await _async_resolve_device_registry(hass, device_registry)

    if device_registry is None:
        return

    snapshot_dict: dict[str, Any]
    snapshot_dict = dict(snapshot) if isinstance(snapshot, Mapping) else dict(build_entry_snapshot(entry))

    raw_profiles = snapshot_dict.get("profiles")
    profiles_map: dict[str, dict[str, Any]] = {}
    orphan_profiles: list[dict[str, Any]] = []
    if isinstance(raw_profiles, Mapping):
        for pid, payload in raw_profiles.items():
            canonical_pid = _normalise_profile_identifier(pid)
            if not canonical_pid:
                if isinstance(payload, Mapping):
                    orphan_profiles.append(_coerce_mapping(payload))
                continue
            if isinstance(payload, Mapping):
                profiles_map[canonical_pid] = _coerce_mapping(payload)
            else:
                profiles_map.setdefault(canonical_pid, {})

    def _resolve_profile_id() -> str:
        candidate = _normalise_profile_identifier(profile_id)
        if candidate:
            return candidate

        fallbacks: tuple[Any, ...] = (
            snapshot_dict.get("primary_profile_id"),
            snapshot_dict.get("plant_id"),
            entry.options.get(CONF_PLANT_ID),
            entry.data.get(CONF_PLANT_ID),
            entry.entry_id,
        )
        for fallback in fallbacks:
            resolved = _normalise_profile_identifier(fallback)
            if resolved:
                return resolved
        return "profile"

    canonical_profile_id = _resolve_profile_id()

    if orphan_profiles:
        merged_orphan_payload: dict[str, Any] = {}
        existing = profiles_map.get(canonical_profile_id)
        if isinstance(existing, Mapping):
            merged_orphan_payload.update(existing)
        for payload in orphan_profiles:
            merged_orphan_payload.update(payload)
        if merged_orphan_payload:
            profiles_map[canonical_profile_id] = merged_orphan_payload
        else:
            profiles_map.setdefault(canonical_profile_id, {})

    if isinstance(profile_payload, Mapping):
        incoming_payload = _coerce_mapping(profile_payload)
        existing_payload = profiles_map.get(canonical_profile_id)
        if isinstance(existing_payload, Mapping) and existing_payload:
            merged_payload = dict(existing_payload)
            merged_payload.update(incoming_payload)
            profiles_map[canonical_profile_id] = merged_payload
        else:
            profiles_map[canonical_profile_id] = incoming_payload
    else:
        profiles_map.setdefault(canonical_profile_id, {})

    if profiles_map:
        snapshot_dict["profiles"] = profiles_map

    plant_id = _normalise_profile_identifier(snapshot_dict.get("plant_id"))
    if plant_id:
        snapshot_dict["plant_id"] = plant_id
    else:
        plant_id = canonical_profile_id
        snapshot_dict["plant_id"] = plant_id

    plant_name = snapshot_dict.get("plant_name")
    if not isinstance(plant_name, str) or not plant_name.strip():
        candidate_payload = profiles_map.get(canonical_profile_id)
        name: str | None = None
        if isinstance(candidate_payload, Mapping):
            general = candidate_payload.get("general")
            if isinstance(general, Mapping):
                display = general.get("display_name") or general.get("name")
                if isinstance(display, str) and display.strip():
                    name = display.strip()
            if not name:
                raw_name = candidate_payload.get("name")
                if isinstance(raw_name, str) and raw_name.strip():
                    name = raw_name.strip()
        if not name:
            name = entry.data.get(CONF_PLANT_NAME)
            if isinstance(name, str):
                name = name.strip()
        snapshot_dict["plant_name"] = name or canonical_profile_id
        plant_name = snapshot_dict["plant_name"]

    primary_profile_id = _normalise_profile_identifier(snapshot_dict.get("primary_profile_id"))
    if primary_profile_id:
        snapshot_dict["primary_profile_id"] = primary_profile_id
    else:
        snapshot_dict["primary_profile_id"] = plant_id
        primary_profile_id = plant_id
    if (
        not isinstance(snapshot_dict.get("primary_profile_name"), str)
        or not str(snapshot_dict.get("primary_profile_name")).strip()
    ):
        snapshot_dict["primary_profile_name"] = plant_name

    entry_info = _normalise_device_info(build_entry_device_info(entry, snapshot_dict))
    entry_kwargs = _clean_device_kwargs(entry_info)
    entry_identifier = entry_device_identifier(entry.entry_id)
    entry_identifiers = entry_kwargs.get("identifiers")
    if not isinstance(entry_identifiers, set) or not entry_identifiers:
        entry_identifiers = _coerce_device_identifiers(entry_identifiers)
    if not entry_identifiers:
        entry_identifiers = {entry_identifier}
    if entry_identifier not in entry_identifiers:
        entry_identifiers.add(entry_identifier)
    entry_kwargs["identifiers"] = entry_identifiers

    entry_device_result = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        **entry_kwargs,
    )
    if inspect.isawaitable(entry_device_result):
        entry_device_result = await entry_device_result

    _entry_device, entry_device_id = _coerce_device_registry_entry(entry_device_result)

    default_name = None
    if isinstance(plant_id, str) and plant_id == canonical_profile_id:
        default_name = plant_name if isinstance(plant_name, str) else None

    profile_info = _normalise_device_info(
        build_profile_device_info(
            entry.entry_id,
            canonical_profile_id,
            profiles_map.get(canonical_profile_id),
            snapshot_dict,
            default_name=default_name,
        )
    )
    profile_kwargs = _clean_device_kwargs(profile_info)
    profile_identifier = profile_device_identifier(entry.entry_id, canonical_profile_id)
    identifiers = profile_kwargs.get("identifiers")
    if not isinstance(identifiers, set) or not identifiers:
        identifiers = _coerce_device_identifiers(identifiers)
    if not identifiers:
        identifiers = {profile_identifier}
    if profile_identifier not in identifiers:
        identifiers.add(profile_identifier)
    profile_kwargs["identifiers"] = identifiers
    profile_device_result = await _async_device_registry_get_or_create(
        device_registry,
        entry,
        profile_kwargs,
        entry_identifier,
        entry_device_id,
    )

    profile_device, raw_profile_device_id = _coerce_device_registry_entry(profile_device_result)

    def _coerce_device_id(value: Any) -> str | None:
        if value is None:
            return None
        if isinstance(value, str):
            text = value.strip()
            return text or None
        try:
            text = str(value)
        except Exception:  # pragma: no cover - defensive conversion
            return None
        text = text.strip()
        return text or None

    profile_device_id = _coerce_device_id(raw_profile_device_id)

    def _is_device_object(candidate: Any) -> bool:
        return isinstance(candidate, Mapping) or hasattr(candidate, "__dict__")

    async def _async_lookup_device(identifier: tuple[str, str]) -> tuple[Any | None, str | None]:
        lookup = getattr(device_registry, "async_get_device", None)
        if not callable(lookup):
            return None, None
        try:
            result = lookup(identifiers={identifier})
        except TypeError:
            try:
                result = lookup({identifier})
            except TypeError:  # pragma: no cover - incompatible signature
                return None, None
        if inspect.isawaitable(result):
            result = await result
        device, device_id = _coerce_device_registry_entry(result)
        return device, device_id

    if profile_device is None or profile_device_id is None:
        lookup_device, lookup_device_id = await _async_lookup_device(profile_identifier)
        if lookup_device is not None:
            profile_device = lookup_device
            profile_device_id = _coerce_device_id(lookup_device_id)

    if entry_device_id:
        entry_device_id = _coerce_device_id(entry_device_id)

    needs_refresh = False

    if (
        entry_device_id
        and profile_device_id
        and (_coerce_device_id(getattr(profile_device, "via_device_id", None)) != entry_device_id)
    ):
        updater = getattr(device_registry, "async_update_device", None)
        if callable(updater):
            try:
                update_result = updater(
                    profile_device_id,
                    via_device_id=entry_device_id,
                )
            except TypeError:
                try:
                    update_result = updater(
                        device_id=profile_device_id,
                        via_device_id=entry_device_id,
                    )
                except TypeError:  # pragma: no cover - incompatible signature
                    update_result = None
            if inspect.isawaitable(update_result):
                update_result = await update_result
            updated_device, updated_device_id = _coerce_device_registry_entry(update_result)
            updated_device_id = _coerce_device_id(updated_device_id)
            if updated_device_id:
                profile_device_id = updated_device_id
            if _is_device_object(updated_device):
                profile_device = updated_device
            else:
                needs_refresh = True
        else:
            needs_refresh = True
    elif profile_device is None or not _is_device_object(profile_device):
        needs_refresh = True

    if entry_device_id and profile_device_id:
        via_candidate = (
            _coerce_device_id(getattr(profile_device, "via_device_id", None))
            if _is_device_object(profile_device)
            else None
        )
        if via_candidate != entry_device_id:
            needs_refresh = True

    if needs_refresh:
        lookup_device, lookup_device_id = await _async_lookup_device(profile_identifier)
        if lookup_device is not None:
            profile_device = lookup_device
        if lookup_device_id is not None:
            profile_device_id = _coerce_device_id(lookup_device_id)

    domain_data = hass.data.setdefault(DOMAIN, {})
    entry_data = domain_data.get(entry.entry_id)
    if not isinstance(entry_data, dict):
        entry_data = {"config_entry": entry}
        domain_data[entry.entry_id] = entry_data

    previous_profiles_raw = entry_data.get("profile_ids") if isinstance(entry_data, Mapping) else ()
    previous_profiles: set[str] = set()
    if isinstance(previous_profiles_raw, Iterable):
        for pid in previous_profiles_raw:
            canonical = _normalise_profile_identifier(pid)
            if canonical:
                previous_profiles.add(canonical)

    entry_data["config_entry"] = entry
    entry_data["snapshot"] = dict(snapshot_dict)
    entry_data["data"] = dict(entry.data)
    entry_data["plant_id"] = snapshot_dict.get("plant_id")
    entry_data["plant_name"] = snapshot_dict.get("plant_name")
    entry_data["primary_profile_id"] = snapshot_dict.get("primary_profile_id")
    entry_data["primary_profile_name"] = snapshot_dict.get("primary_profile_name")

    plant_identifier = entry_data.get("plant_id")
    if isinstance(plant_identifier, str) and plant_identifier:
        entry_data["profile_dir"] = Path(hass.config.path("plants")) / plant_identifier

    entry_data["entry_device_info"] = entry_info
    entry_data["entry_device_identifier"] = entry_identifier

    stored_profiles = entry_data.get("profiles")
    merged_profiles: dict[str, Mapping[str, Any]] = {}
    if isinstance(stored_profiles, Mapping):
        for pid, payload in stored_profiles.items():
            canonical_pid = _normalise_profile_identifier(pid)
            if not canonical_pid:
                continue
            if isinstance(payload, Mapping):
                merged_profiles[canonical_pid] = _coerce_mapping(payload)
            else:
                merged_profiles.setdefault(canonical_pid, {})

    profile_payload = profiles_map.get(canonical_profile_id)
    if isinstance(profile_payload, Mapping):
        merged_profiles[canonical_profile_id] = _coerce_mapping(profile_payload)
    else:
        merged_profiles.setdefault(canonical_profile_id, {})

    entry_data["profiles"] = merged_profiles

    profile_ids = {pid for pid in merged_profiles if isinstance(pid, str) and pid}
    if isinstance(plant_id, str) and plant_id:
        profile_ids.add(plant_id)
    if isinstance(primary_profile_id, str) and primary_profile_id:
        profile_ids.add(primary_profile_id)
    profile_ids.add(canonical_profile_id)
    entry_data["profile_ids"] = sorted(profile_ids)

    profile_devices = entry_data.get("profile_devices")
    merged_devices: dict[str, Mapping[str, Any]] = {}
    if isinstance(profile_devices, Mapping):
        for pid, payload in profile_devices.items():
            canonical_pid = _normalise_profile_identifier(pid)
            if not canonical_pid:
                continue
            if isinstance(payload, Mapping):
                merged_devices[canonical_pid] = _normalise_device_info(payload)
    merged_devices[canonical_profile_id] = profile_info
    entry_data["profile_devices"] = merged_devices

    profile_contexts = entry_data.get("profile_contexts")
    merged_contexts: dict[str, Mapping[str, Any]] = {}
    if isinstance(profile_contexts, Mapping):
        for pid, payload in profile_contexts.items():
            canonical_pid = _normalise_profile_identifier(pid)
            if not canonical_pid:
                continue
            if isinstance(payload, Mapping):
                merged_contexts[canonical_pid] = dict(payload)
    merged_contexts[canonical_profile_id] = _build_profile_context(
        entry,
        snapshot_dict,
        canonical_profile_id,
        profiles_map.get(canonical_profile_id),
    )
    entry_data["profile_contexts"] = merged_contexts

    by_pid = domain_data.setdefault(BY_PLANT_ID, {})
    for pid in profile_ids:
        if isinstance(pid, str) and pid:
            by_pid[pid] = entry_data

    current_profiles = tuple(pid for pid in entry_data["profile_ids"] if pid)
    current_profile_set = set(current_profiles)
    added_profiles = tuple(pid for pid in current_profiles if pid not in previous_profiles)
    removed_profiles = tuple(pid for pid in previous_profiles if pid not in current_profile_set)
    updated_profiles: tuple[str, ...] = ()
    if canonical_profile_id in previous_profiles and canonical_profile_id not in removed_profiles:
        updated_profiles = (canonical_profile_id,)

    if added_profiles or removed_profiles or updated_profiles:
        async_dispatcher_send(
            hass,
            signal_profile_contexts_updated(entry.entry_id),
            {
                "added": added_profiles,
                "removed": removed_profiles,
                "updated": updated_profiles,
            },
        )

    return None


async def ensure_all_profile_devices_registered(
    hass: HomeAssistant,
    entry: ConfigEntry,
    *,
    snapshot: Mapping[str, Any] | None = None,
    extra_profiles: Mapping[str, Mapping[str, Any]] | None = None,
) -> None:
    """Ensure every profile in ``entry`` has a corresponding device."""

    device_registry = await _async_resolve_device_registry(hass)

    if device_registry is None:
        return

    if isinstance(snapshot, Mapping):
        snapshot_dict: dict[str, Any] = dict(snapshot)
    else:
        snapshot_dict = dict(build_entry_snapshot(entry))

    canonical_profiles: dict[str, Mapping[str, Any] | None] = {}

    raw_profiles = snapshot_dict.get("profiles")
    if isinstance(raw_profiles, Mapping):
        for pid, payload in raw_profiles.items():
            canonical_pid = _normalise_profile_identifier(pid)
            if not canonical_pid:
                continue
            if isinstance(payload, Mapping):
                canonical_profiles[canonical_pid] = payload
            else:
                canonical_profiles.setdefault(canonical_pid, None)

    if isinstance(extra_profiles, Mapping):
        for pid, payload in extra_profiles.items():
            canonical_pid = _normalise_profile_identifier(pid)
            if not canonical_pid:
                continue
            if isinstance(payload, Mapping):
                canonical_profiles[canonical_pid] = payload
            elif canonical_pid not in canonical_profiles:
                canonical_profiles[canonical_pid] = None

    if canonical_profiles:
        snapshot_dict["profiles"] = {
            pid: _coerce_mapping(payload) for pid, payload in canonical_profiles.items() if isinstance(payload, Mapping)
        }
        for pid, payload in canonical_profiles.items():
            await ensure_profile_device_registered(
                hass,
                entry,
                pid,
                payload if isinstance(payload, Mapping) else None,
                snapshot=snapshot_dict,
                device_registry=device_registry,
            )
        return

    fallback_id = _normalise_profile_identifier(snapshot_dict.get("plant_id"))
    if not fallback_id:
        candidate = entry.data.get(CONF_PLANT_ID)
        fallback_id = _normalise_profile_identifier(candidate) if candidate is not None else ""
        if not fallback_id:
            fallback_id = str(entry.entry_id)

    await ensure_profile_device_registered(
        hass,
        entry,
        fallback_id,
        None,
        snapshot=snapshot_dict,
        device_registry=device_registry,
    )


async def backfill_profile_devices_from_options(
    hass: HomeAssistant,
    entry: ConfigEntry,
    entry_data: Mapping[str, Any] | None = None,
) -> bool:
    """Backfill missing profile devices when options outpace metadata refresh.

    The config options flow can add or import profiles before
    :func:`update_entry_data` or other snapshot helpers have a chance to
    regenerate the cached entry metadata. Compare the currently stored devices
    against the config entry's ``profiles`` mapping and register any missing
    devices so they appear beneath the integration entry immediately. Returns
    ``True`` when new devices were scheduled for registration.
    """

    stored: Mapping[str, Any] | None
    stored = entry_data if isinstance(entry_data, Mapping) else get_entry_data(hass, entry)

    if not isinstance(stored, Mapping):
        return False

    raw_profiles = entry.options.get(CONF_PROFILES)
    if not isinstance(raw_profiles, Mapping) or not raw_profiles:
        return False

    recorded_devices = stored.get("profile_devices")
    existing_ids: set[str] = set()
    if isinstance(recorded_devices, Mapping):
        for pid in recorded_devices:
            canonical_pid = _normalise_profile_identifier(pid)
            if canonical_pid:
                existing_ids.add(canonical_pid)

    missing: dict[str, Mapping[str, Any]] = {}
    for pid, payload in raw_profiles.items():
        canonical_pid = _normalise_profile_identifier(pid)
        if not canonical_pid or not isinstance(payload, Mapping):
            continue
        if canonical_pid not in existing_ids:
            missing[canonical_pid] = payload

    if not missing:
        return False

    snapshot = stored.get("snapshot")
    snapshot_map = snapshot if isinstance(snapshot, Mapping) else None

    await ensure_all_profile_devices_registered(
        hass,
        entry,
        snapshot=snapshot_map,
        extra_profiles=missing,
    )

    return True


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
        if not domain_data or (set(domain_data.keys()) <= {BY_PLANT_ID} and not domain_data.get(BY_PLANT_ID)):
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


def serialise_device_info(
    info: Mapping[str, Any] | None,
    *,
    fallback_identifier: Any | None = None,
    fallback_via_device: Any | None = None,
) -> dict[str, Any]:
    """Return a JSON-friendly representation of ``info``."""

    payload: dict[str, Any] = {}

    normalised = _normalise_device_info(info)

    identifier_pairs: set[tuple[str, str]] = set()
    raw_identifiers = normalised.get("identifiers")
    if isinstance(raw_identifiers, Set):
        for item in raw_identifiers:
            pair = _as_identifier_pair(item)
            if pair:
                identifier_pairs.add((str(pair[0]), str(pair[1])))
    else:
        identifier_pairs = _coerce_device_identifiers(raw_identifiers)

    def _add_identifier(candidate: Any | None) -> None:
        if candidate is None:
            return
        pair = _as_identifier_pair(candidate)
        if pair is None and isinstance(candidate, str) and candidate:
            pair = (DOMAIN, candidate)
        if pair:
            identifier_pairs.add((str(pair[0]), str(pair[1])))

    _add_identifier(fallback_identifier)

    if identifier_pairs:
        payload["identifiers"] = _serialise_identifier_set(identifier_pairs)

    connection_pairs = _coerce_device_identifiers(normalised.get("connections"))
    if connection_pairs:
        payload["connections"] = _serialise_identifier_set(connection_pairs)

    via_pair = _as_identifier_pair(normalised.get("via_device"))
    if via_pair is None and fallback_via_device is not None:
        via_pair = _as_identifier_pair(fallback_via_device)
        if via_pair is None and isinstance(fallback_via_device, str) and fallback_via_device:
            via_pair = (DOMAIN, fallback_via_device)
    if via_pair:
        payload["via_device"] = {"domain": str(via_pair[0]), "id": str(via_pair[1])}

    for key, value in normalised.items():
        if key in {"identifiers", "connections", "via_device"}:
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
        return _clean_device_kwargs(_normalise_device_info(build_entry_device_info(entry, snapshot)))
    return None


def resolve_profile_device_info(
    hass: HomeAssistant,
    entry_id: str | None,
    profile_id: str,
) -> dict[str, Any] | None:
    """Return device info for ``profile_id`` attached to ``entry_id``."""

    canonical_profile_id = _normalise_profile_identifier(profile_id)
    if not canonical_profile_id:
        return None

    stored = None
    if entry_id:
        stored = get_entry_data(hass, entry_id)
    if stored is None:
        stored = get_entry_data_by_plant_id(hass, canonical_profile_id)
    if stored is None:
        return None

    profile_devices = stored.get("profile_devices")
    if isinstance(profile_devices, Mapping):
        payload = profile_devices.get(canonical_profile_id)
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
                canonical_profile_id,
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

    def _normalise_image(value: Any) -> str | None:
        if isinstance(value, str):
            text = value.strip()
            if text:
                return text
        return None

    def _image_from_payload(payload: Mapping[str, Any] | None) -> str | None:
        if not isinstance(payload, Mapping):
            return None
        for key in ("image_url", "image", "picture"):
            candidate = _normalise_image(payload.get(key))
            if candidate:
                return candidate
        general = payload.get("general") if isinstance(payload.get("general"), Mapping) else None
        if general:
            image = _image_from_payload(general)
            if image:
                return image
        return None

    canonical_profile_id: str | None = None
    if profile_id is not None:
        canonical_profile_id = _normalise_profile_identifier(profile_id)
        if not canonical_profile_id:
            canonical_profile_id = None

    stored: dict | None = None
    if entry_id:
        stored = get_entry_data(hass, entry_id)
    if stored is None and canonical_profile_id:
        stored = get_entry_data_by_plant_id(hass, canonical_profile_id)
    if not stored:
        return None

    snapshot = stored.get("snapshot")
    if isinstance(snapshot, Mapping):
        profiles = snapshot.get("profiles")
        if isinstance(profiles, Mapping) and canonical_profile_id:
            profile = profiles.get(canonical_profile_id)
            image = _image_from_payload(profile) if isinstance(profile, Mapping) else None
            if image:
                return image
        primary_id = snapshot.get("primary_profile_id")
        if (
            isinstance(primary_id, str)
            and primary_id
            and canonical_profile_id
            and _normalise_profile_identifier(primary_id) == canonical_profile_id
        ):
            primary_profile = snapshot.get("primary_profile")
            image = _image_from_payload(primary_profile) if isinstance(primary_profile, Mapping) else None
            if image:
                return image

    entry = stored.get("config_entry")
    if entry is None:
        return None
    image_url = _normalise_image(entry.options.get("image_url"))
    if image_url:
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

    canonical_profile_id = _normalise_profile_identifier(profile_id)
    if canonical_profile_id:
        profile_id = canonical_profile_id

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

    metrics = context.get("metrics")
    if not isinstance(metrics, Mapping):
        metrics = _resolve_profile_metrics(payload, thresholds=thresholds)

    return ProfileContext(
        id=profile_id,
        name=name,
        sensors=sensors,
        thresholds=thresholds,
        metrics=metrics,
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

    metrics = _resolve_profile_metrics(payload, thresholds=thresholds)

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
        metrics=metrics,
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

    stored_raw = get_entry_data(hass, entry)
    stored: Mapping[str, Any]
    stored = dict(stored_raw) if isinstance(stored_raw, Mapping) else {}

    snapshot = stored.get("snapshot") if isinstance(stored.get("snapshot"), Mapping) else None
    if snapshot is None:
        snapshot = build_entry_snapshot(entry)
        stored["snapshot"] = snapshot
        profiles_payload = snapshot.get("profiles")
        if isinstance(profiles_payload, Mapping):
            stored.setdefault("profiles", profiles_payload)
        stored.setdefault("plant_id", snapshot.get("plant_id"))
        stored.setdefault("plant_name", snapshot.get("plant_name"))
        stored.setdefault("primary_profile_id", snapshot.get("primary_profile_id"))
        stored.setdefault("primary_profile_name", snapshot.get("primary_profile_name"))

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
