"""Device triggers for Horticulture Assistant plant profiles."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.components.automation import state as state_trigger
from homeassistant.components.device_automation import DEVICE_TRIGGER_BASE_SCHEMA
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN

TRIGGER_STATUS_PROBLEM = "status_problem"
TRIGGER_STATUS_RECOVERED = "status_recovered"
TRIGGER_STATUS_CHANGED = "status_changed"

TRIGGER_TYPES: set[str] = {
    TRIGGER_STATUS_PROBLEM,
    TRIGGER_STATUS_RECOVERED,
    TRIGGER_STATUS_CHANGED,
}

TRIGGER_SCHEMA = DEVICE_TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Required("type"): vol.In(TRIGGER_TYPES),
        vol.Optional("to"): vol.Any(cv.string, [cv.string]),
        vol.Optional("from"): vol.Any(cv.string, [cv.string]),
        vol.Optional("for"): cv.positive_time_period_dict,
    }
)


async def async_get_triggers(hass: HomeAssistant, device_id: str) -> list[dict[str, Any]]:
    """Return device triggers for a Horticulture Assistant profile."""

    registry = er.async_get(hass)
    triggers: list[dict[str, Any]] = []

    for entry in registry.entities.values():
        if entry.device_id != device_id or entry.domain != "sensor":
            continue
        if not entry.entity_id or not entry.unique_id:
            continue
        if not entry.unique_id.endswith(":status"):
            continue
        base = {
            "platform": "device",
            "domain": DOMAIN,
            "device_id": device_id,
            "entity_id": entry.entity_id,
            "metadata": {"secondary": False},
        }
        triggers.append({**base, "type": TRIGGER_STATUS_PROBLEM})
        triggers.append({**base, "type": TRIGGER_STATUS_RECOVERED})
        triggers.append({**base, "type": TRIGGER_STATUS_CHANGED, "metadata": {"secondary": True}})

    return triggers


async def async_get_trigger_capabilities(
    hass: HomeAssistant,
    config: dict[str, Any],
) -> dict[str, vol.Schema]:
    """Return trigger capabilities for the given configuration."""

    trigger_type = config.get("type")
    if trigger_type == TRIGGER_STATUS_CHANGED:
        extra = {
            vol.Optional("from"): vol.Any(cv.string, [cv.string]),
            vol.Optional("to"): vol.Any(cv.string, [cv.string]),
            vol.Optional("for"): cv.positive_time_period_dict,
        }
    else:
        extra = {vol.Optional("for"): cv.positive_time_period_dict}
    return {"extra_fields": vol.Schema(extra)}


async def async_attach_trigger(
    hass: HomeAssistant,
    config: dict[str, Any],
    action,
    automation_info,
):
    """Attach a device trigger for the given configuration."""

    validated = TRIGGER_SCHEMA(config)
    entity_id: str = validated["entity_id"]
    trigger_type: str = validated["type"]

    state_config: dict[str, Any] = {"entity_id": entity_id}

    if trigger_type == TRIGGER_STATUS_PROBLEM:
        state_config["to"] = ["warn", "critical"]
    elif trigger_type == TRIGGER_STATUS_RECOVERED:
        state_config["to"] = "ok"
    else:  # TRIGGER_STATUS_CHANGED
        if "to" in validated:
            state_config["to"] = validated["to"]
        if "from" in validated:
            state_config["from"] = validated["from"]

    if "for" in validated:
        state_config["for"] = validated["for"]

    return await state_trigger.async_attach_trigger(
        hass,
        state_config,
        action,
        automation_info,
        platform_type="device",
    )


__all__ = [
    "async_get_triggers",
    "async_get_trigger_capabilities",
    "async_attach_trigger",
]
