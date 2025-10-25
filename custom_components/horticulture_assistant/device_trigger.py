"""Device triggers for Horticulture Assistant plant profiles."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

import voluptuous as vol

try:  # pragma: no cover - exercised in CI when Home Assistant isn't installed
    from homeassistant.components.automation import event as event_trigger
    from homeassistant.components.automation import state as state_trigger
    from homeassistant.components.device_automation import DEVICE_TRIGGER_BASE_SCHEMA
    from homeassistant.const import EVENT_STATE_CHANGED
    from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
    from homeassistant.exceptions import InvalidDeviceAutomationConfig
    from homeassistant.helpers import config_validation as cv, entity_registry as er
except ModuleNotFoundError:  # pragma: no cover - lightweight shim for unit tests
    import types

    CALLBACK_TYPE = Callable[[], None]
    HomeAssistant = Any  # type: ignore[assignment]

    def callback(func):  # type: ignore[override]
        return func

    class InvalidDeviceAutomationConfig(Exception):
        """Fallback exception used during lightweight tests."""

    def _identity(value):  # type: ignore[override]
        return value

    cv = types.SimpleNamespace(  # type: ignore[assignment]
        entity_id=_identity,
        string=str,
        positive_time_period_dict=_identity,
    )

    er = types.SimpleNamespace(  # type: ignore[assignment]
        async_get=lambda _hass: types.SimpleNamespace(  # type: ignore[arg-type]
            entities={},
            async_get=lambda _entity_id: None,
        ),
        async_entries_for_device=lambda _registry, _device_id, include_disabled_entities=False: [],
    )

    EVENT_STATE_CHANGED = "state_changed"

    async def _fallback_async_attach_event_trigger(hass, config, action, _automation_info, *, platform_type="event"):
        event_type = config.get("event_type")
        if not event_type:
            raise InvalidDeviceAutomationConfig("event trigger missing event_type")
        expected = dict(config.get("event_data") or {})

        @callback
        def _handle(event):
            data = event.data or {}
            for key, value in expected.items():
                if data.get(key) != value:
                    return

            trigger_data = {
                "platform": platform_type,
                "event": event,
                "event_data": data,
            }
            hass.async_create_task(action(trigger_data, {}, event.context))

        return hass.bus.async_listen(event_type, _handle)

    async def _fallback_async_attach_state_trigger(hass, config, action, _automation_info, *, platform_type="state"):
        entity_id = config.get("entity_id")
        if not entity_id:
            raise InvalidDeviceAutomationConfig("state trigger missing entity_id")
        to_value = config.get("to")
        from_value = config.get("from")

        if isinstance(to_value, list):
            to_values = {str(item) for item in to_value}
        elif to_value is None:
            to_values = None
        else:
            to_values = {str(to_value)}

        if isinstance(from_value, list):
            from_values = {str(item) for item in from_value}
        elif from_value is None:
            from_values = None
        else:
            from_values = {str(from_value)}

        @callback
        def _handle(event):
            if event.data.get("entity_id") != entity_id:
                return
            old_state = event.data.get("old_state")
            new_state = event.data.get("new_state")
            if from_values is not None:
                if old_state is None or old_state.state not in from_values:
                    return
            if to_values is not None:
                if new_state is None:
                    return
                if new_state.state not in to_values:
                    return

            trigger_data = {
                "platform": platform_type,
                "entity_id": entity_id,
                "from_state": old_state,
                "to_state": new_state,
            }
            hass.async_create_task(action(trigger_data, {}, event.context))

        return hass.bus.async_listen(EVENT_STATE_CHANGED, _handle)

    DEVICE_TRIGGER_BASE_SCHEMA = vol.Schema({})

    event_trigger = types.SimpleNamespace(async_attach_trigger=_fallback_async_attach_event_trigger)
    state_trigger = types.SimpleNamespace(async_attach_trigger=_fallback_async_attach_state_trigger)

from .const import (
    DOMAIN,
    EVENT_PROFILE_CULTIVATION_RECORDED,
    EVENT_PROFILE_HARVEST_RECORDED,
    EVENT_PROFILE_NUTRIENT_RECORDED,
    EVENT_PROFILE_RUN_RECORDED,
    STATUS_OK,
    STATUS_STATES_PROBLEM,
)


TRIGGER_STATUS_PROBLEM = "status_problem"
TRIGGER_STATUS_RECOVERED = "status_recovered"
TRIGGER_STATUS_CHANGED = "status_changed"
TRIGGER_RUN_RECORDED = "run_recorded"
TRIGGER_HARVEST_RECORDED = "harvest_recorded"
TRIGGER_NUTRIENT_RECORDED = "nutrient_recorded"
TRIGGER_CULTIVATION_RECORDED = "cultivation_recorded"

TRIGGER_TYPES: set[str] = {
    TRIGGER_STATUS_PROBLEM,
    TRIGGER_STATUS_RECOVERED,
    TRIGGER_STATUS_CHANGED,
    TRIGGER_RUN_RECORDED,
    TRIGGER_HARVEST_RECORDED,
    TRIGGER_NUTRIENT_RECORDED,
    TRIGGER_CULTIVATION_RECORDED,
}

EVENT_TRIGGER_TYPES: set[str] = {
    TRIGGER_RUN_RECORDED,
    TRIGGER_HARVEST_RECORDED,
    TRIGGER_NUTRIENT_RECORDED,
    TRIGGER_CULTIVATION_RECORDED,
}

EVENT_MAP: dict[str, str] = {
    TRIGGER_RUN_RECORDED: EVENT_PROFILE_RUN_RECORDED,
    TRIGGER_HARVEST_RECORDED: EVENT_PROFILE_HARVEST_RECORDED,
    TRIGGER_NUTRIENT_RECORDED: EVENT_PROFILE_NUTRIENT_RECORDED,
    TRIGGER_CULTIVATION_RECORDED: EVENT_PROFILE_CULTIVATION_RECORDED,
}

TRIGGER_SCHEMA = DEVICE_TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Required("type"): vol.In(TRIGGER_TYPES),
        vol.Optional("to"): vol.Any(cv.string, [cv.string]),
        vol.Optional("from"): vol.Any(cv.string, [cv.string]),
        vol.Optional("for"): cv.positive_time_period_dict,
        vol.Optional("event_subtype"): cv.string,
        vol.Optional("run_id"): cv.string,
    }
)


async def async_get_triggers(hass: HomeAssistant, device_id: str) -> list[dict[str, Any]]:
    """Return device triggers for a Horticulture Assistant profile."""

    registry = er.async_get(hass)
    triggers: list[dict[str, Any]] = []

    entries = er.async_entries_for_device(registry, device_id, include_disabled_entities=True)
    for entry in entries:
        if entry.domain != "sensor" or not entry.unique_id or not entry.entity_id:
            continue
        if ":" not in entry.unique_id:
            continue
        suffix = entry.unique_id.split(":", 1)[1]
        base: dict[str, Any] = {
            "platform": "device",
            "domain": DOMAIN,
            "device_id": device_id,
            "entity_id": entry.entity_id,
            "metadata": {"secondary": False},
        }
        if suffix == "status":
            triggers.append(base | {"type": TRIGGER_STATUS_PROBLEM})
            triggers.append(base | {"type": TRIGGER_STATUS_RECOVERED})
            triggers.append(base | {"type": TRIGGER_STATUS_CHANGED, "metadata": {"secondary": True}})
        elif suffix == "run_status":
            triggers.append(base | {"type": TRIGGER_RUN_RECORDED, "metadata": {"secondary": True}})
        elif suffix == "yield_total":
            triggers.append(base | {"type": TRIGGER_HARVEST_RECORDED, "metadata": {"secondary": True}})
        elif suffix == "feeding_status":
            triggers.append(base | {"type": TRIGGER_NUTRIENT_RECORDED, "metadata": {"secondary": True}})
        elif suffix == "event_activity":
            triggers.append(base | {"type": TRIGGER_CULTIVATION_RECORDED, "metadata": {"secondary": True}})

    return triggers


async def async_get_trigger_capabilities(
    hass: HomeAssistant,
    config: dict[str, Any],
) -> dict[str, vol.Schema]:
    """Return trigger capabilities for the given configuration."""

    trigger_type = config.get("type")
    if trigger_type in EVENT_TRIGGER_TYPES:
        extra = {
            vol.Optional("event_subtype"): cv.string,
            vol.Optional("run_id"): cv.string,
        }
    elif trigger_type == TRIGGER_STATUS_CHANGED:
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
    config: Mapping[str, Any],
    action,
    automation_info,
) -> CALLBACK_TYPE:
    """Attach a device trigger for the given configuration."""

    validated = TRIGGER_SCHEMA(dict(config))
    entity_id: str = validated["entity_id"]
    trigger_type: str = validated["type"]

    registry = er.async_get(hass)
    entry = registry.async_get(entity_id)
    if entry is None or not entry.unique_id or ":" not in entry.unique_id:
        raise InvalidDeviceAutomationConfig("unable to resolve profile for device trigger")
    profile_id = entry.unique_id.split(":", 1)[0]

    if trigger_type in EVENT_TRIGGER_TYPES:
        event_type = EVENT_MAP[trigger_type]
        event_data: dict[str, Any] = {"profile_id": profile_id}
        if "run_id" in validated:
            event_data["run_id"] = validated["run_id"]
        if "event_subtype" in validated:
            event_data["event_subtype"] = validated["event_subtype"]
        event_config = {"event_type": event_type, "event_data": event_data}
        return await event_trigger.async_attach_trigger(
            hass,
            event_config,
            action,
            automation_info,
            platform_type="device",
        )

    state_config: dict[str, Any] = {"entity_id": entity_id}

    if trigger_type == TRIGGER_STATUS_PROBLEM:
        state_config["to"] = list(STATUS_STATES_PROBLEM)
    elif trigger_type == TRIGGER_STATUS_RECOVERED:
        state_config["to"] = STATUS_OK
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
