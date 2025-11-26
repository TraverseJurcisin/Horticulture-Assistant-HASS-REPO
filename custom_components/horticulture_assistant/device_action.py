"""Device actions for Horticulture Assistant plant profiles."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol

try:  # pragma: no cover - exercised in CI when Home Assistant isn't installed
    from homeassistant.components.device_automation import DEVICE_ACTION_BASE_SCHEMA
    from homeassistant.core import Context, HomeAssistant
    from homeassistant.exceptions import InvalidDeviceAutomationConfig
    from homeassistant.helpers import config_validation as cv
    from homeassistant.helpers import device_registry as dr
    from homeassistant.helpers import entity_registry as er
except ModuleNotFoundError:  # pragma: no cover - lightweight shim for unit tests
    import types

    Context = Any  # type: ignore[assignment]
    HomeAssistant = Any  # type: ignore[assignment]

    class InvalidDeviceAutomationConfig(Exception):
        """Fallback exception used during lightweight tests."""

    def _identity(value):  # type: ignore[override]
        return value

    DEVICE_ACTION_BASE_SCHEMA = vol.Schema({})
    cv = types.SimpleNamespace(  # type: ignore[assignment]
        entity_id=_identity,
        string=_identity,
    )

    class _DeviceRegistryStub:
        def __init__(self):
            self.devices: dict[str, Any] = {}

        def async_get(self, device_id):
            return self.devices.get(device_id)

    class _EntityRegistryStub:
        def __init__(self):
            self.entities: dict[str, Any] = {}

        def async_entries_for_device(self, _registry, _device_id, include_disabled_entities=False):
            return list(self.entities.values())

    dr = types.SimpleNamespace(async_get=lambda _hass: _DeviceRegistryStub())
    er = types.SimpleNamespace(async_get=lambda _hass: _EntityRegistryStub())

from .const import DOMAIN
from .services import MEASUREMENT_CLASSES, SERVICE_REPLACE_SENSOR

ACTION_REPLACE_SENSORS = "replace_sensors"

ACTION_TYPES: set[str] = {
    ACTION_REPLACE_SENSORS,
}


def _normalise_profile_id(value: Any) -> str:
    if isinstance(value, str):
        text = value.strip()
    elif value is None:
        text = ""
    else:
        text = str(value).strip()
    if text.lower().startswith("profile:"):
        return text.split(":", 1)[1].strip()
    return text


def _resolve_profile_id(hass: HomeAssistant, device_id: str) -> str | None:
    """Return the plant profile identifier associated with ``device_id``."""

    device_registry = dr.async_get(hass)
    device_entry = device_registry.async_get(device_id)
    if device_entry is not None:
        for domain, identifier in getattr(device_entry, "identifiers", []) or []:
            if domain != DOMAIN or not identifier:
                continue
            profile_id = _normalise_profile_id(identifier)
            if profile_id:
                return profile_id

    entity_registry = er.async_get(hass)
    entries = er.async_entries_for_device(entity_registry, device_id, include_disabled_entities=True)
    for entry in entries:
        unique_id = getattr(entry, "unique_id", None)
        if not unique_id:
            continue
        if ":" in unique_id:
            candidate = unique_id.split(":", 1)[0]
        elif "_" in unique_id:
            candidate = unique_id.split("_", 1)[0]
        else:
            continue
        profile_id = _normalise_profile_id(candidate)
        if profile_id:
            return profile_id
    return None


ACTION_SCHEMA = DEVICE_ACTION_BASE_SCHEMA.extend(
    {
        vol.Required("device_id"): cv.string,
        vol.Required("type"): vol.In(ACTION_TYPES),
        vol.Required("measurement"): vol.In(sorted(MEASUREMENT_CLASSES)),
        vol.Required("entity_id"): cv.entity_id,
    }
)


async def async_get_actions(hass: HomeAssistant, device_id: str) -> list[dict[str, Any]]:
    """Return device actions for a Horticulture Assistant profile."""

    profile_id = _resolve_profile_id(hass, device_id)
    if not profile_id:
        return []

    return [
        {
            "platform": "device",
            "domain": DOMAIN,
            "device_id": device_id,
            "type": ACTION_REPLACE_SENSORS,
            "metadata": {"secondary": False},
        }
    ]


async def async_get_action_capabilities(_hass: HomeAssistant, _config: Mapping[str, Any]) -> dict[str, vol.Schema]:
    """Return action capabilities for the given configuration."""

    return {
        "extra_fields": vol.Schema(
            {
                vol.Required("measurement"): vol.In(sorted(MEASUREMENT_CLASSES)),
                vol.Required("entity_id"): cv.entity_id,
            }
        )
    }


async def async_call_action(
    hass: HomeAssistant,
    config: Mapping[str, Any],
    variables: Mapping[str, Any],
    context: Context | None,
) -> None:
    """Execute a configured device action."""

    _ = variables  # Unused but kept for signature compatibility
    validated = ACTION_SCHEMA(dict(config))
    if validated["type"] != ACTION_REPLACE_SENSORS:
        raise InvalidDeviceAutomationConfig("unsupported device action")

    profile_id = _resolve_profile_id(hass, validated["device_id"])
    if not profile_id:
        raise InvalidDeviceAutomationConfig("unable to resolve profile for device action")

    await hass.services.async_call(
        DOMAIN,
        SERVICE_REPLACE_SENSOR,
        {
            "profile_id": profile_id,
            "measurement": validated["measurement"],
            "entity_id": validated["entity_id"],
        },
        blocking=True,
        context=context,
    )


__all__ = [
    "async_get_actions",
    "async_get_action_capabilities",
    "async_call_action",
    "ACTION_REPLACE_SENSORS",
]
