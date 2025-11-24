"""Device conditions for Horticulture Assistant plant profiles."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

import voluptuous as vol

try:  # pragma: no cover - exercised in CI when Home Assistant isn't installed
    from homeassistant.components.device_automation import DEVICE_CONDITION_BASE_SCHEMA
    from homeassistant.core import HomeAssistant, callback
    from homeassistant.exceptions import InvalidDeviceAutomationConfig
    from homeassistant.helpers import config_validation as cv
    from homeassistant.helpers import entity_registry as er
    from homeassistant.helpers.condition import ConditionCheckerType
except ModuleNotFoundError:  # pragma: no cover - lightweight shim for unit tests
    import types

    HomeAssistant = Any  # type: ignore[assignment]

    def callback(func):  # type: ignore[override]
        return func

    class InvalidDeviceAutomationConfig(Exception):
        """Fallback exception used during lightweight tests."""

    cv = types.SimpleNamespace(  # type: ignore[assignment]
        entity_id=str,
        string=str,
        positive_time_period_dict=lambda value: value,
    )

    er = types.SimpleNamespace(  # type: ignore[assignment]
        async_get=lambda _hass: types.SimpleNamespace(  # type: ignore[arg-type]
            entities={},
            async_get=lambda _entity_id: None,
            async_entries_for_device=lambda _registry, _device_id, include_disabled_entities=False: [],
        ),
        async_entries_for_device=lambda _registry, _device_id, include_disabled_entities=False: [],
    )

    ConditionCheckerType = Callable[[HomeAssistant, Mapping[str, Any]], bool]
    DEVICE_CONDITION_BASE_SCHEMA = vol.Schema({})

from .const import DOMAIN, STATUS_STATES_PROBLEM, STATUS_STATES_RECOVERED

CONDITION_STATUS_IS = "status_is"
CONDITION_STATUS_OK = "status_ok"
CONDITION_STATUS_PROBLEM = "status_problem"
CONDITION_STATUS_RECOVERED = "status_recovered"
CONDITION_RUN_ACTIVE = "run_active"

CONDITION_TYPES: set[str] = {
    CONDITION_STATUS_IS,
    CONDITION_STATUS_OK,
    CONDITION_STATUS_PROBLEM,
    CONDITION_STATUS_RECOVERED,
    CONDITION_RUN_ACTIVE,
}


def _normalise_states(value: Any | None) -> set[str]:
    if value is None:
        return set()
    if isinstance(value, str):
        return {value}
    try:
        return {str(item) for item in value}
    except TypeError:  # value is not iterable
        return {str(value)}


CONDITION_SCHEMA = DEVICE_CONDITION_BASE_SCHEMA.extend(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Required("type"): vol.In(CONDITION_TYPES),
        vol.Optional("state"): vol.Any(cv.string, [cv.string]),
    }
)


async def async_get_conditions(hass: HomeAssistant, device_id: str) -> list[dict[str, Any]]:
    """Return device conditions for a Horticulture Assistant profile."""

    registry = er.async_get(hass)
    entries = er.async_entries_for_device(registry, device_id, include_disabled_entities=True)
    conditions: list[dict[str, Any]] = []

    for entry in entries:
        if entry.domain != "sensor" or not entry.unique_id or not entry.entity_id:
            continue
        suffix = None
        if ":" in entry.unique_id:
            suffix = entry.unique_id.split(":", 1)[1]
        elif "_" in entry.unique_id:
            suffix = entry.unique_id.rsplit("_", 1)[1]
        if not suffix:
            continue
        base: dict[str, Any] = {
            "platform": "device",
            "domain": DOMAIN,
            "device_id": device_id,
            "entity_id": entry.entity_id,
        }
        if suffix == "status":
            conditions.extend(
                [
                    base | {"type": CONDITION_STATUS_IS},
                    base | {"type": CONDITION_STATUS_OK, "metadata": {"secondary": True}},
                    base | {"type": CONDITION_STATUS_PROBLEM, "metadata": {"secondary": True}},
                    base | {"type": CONDITION_STATUS_RECOVERED, "metadata": {"secondary": True}},
                ]
            )
        elif suffix == "run_status":
            conditions.append(base | {"type": CONDITION_RUN_ACTIVE, "metadata": {"secondary": True}})

    return conditions


async def async_get_condition_capabilities(hass: HomeAssistant, config: Mapping[str, Any]) -> dict[str, vol.Schema]:
    """Return condition capabilities for the given configuration."""

    condition_type = config.get("type")
    extra = {vol.Required("state"): vol.Any(cv.string, [cv.string])} if condition_type == CONDITION_STATUS_IS else {}
    return {"extra_fields": vol.Schema(extra)}


async def async_condition_from_config(hass: HomeAssistant, config: Mapping[str, Any]) -> ConditionCheckerType:
    """Create a condition function for the provided configuration."""

    validated = CONDITION_SCHEMA(dict(config))
    entity_id: str = validated["entity_id"]
    condition_type: str = validated["type"]

    registry = er.async_get(hass)
    entry = registry.async_get(entity_id)
    if entry is None or not entry.unique_id or ":" not in entry.unique_id:
        raise InvalidDeviceAutomationConfig("unable to resolve profile for device condition")
    suffix = entry.unique_id.split(":", 1)[1]

    if condition_type in {
        CONDITION_STATUS_IS,
        CONDITION_STATUS_OK,
        CONDITION_STATUS_PROBLEM,
        CONDITION_STATUS_RECOVERED,
    }:
        if suffix != "status":
            raise InvalidDeviceAutomationConfig("device condition must target a status sensor")
        if condition_type == CONDITION_STATUS_IS:
            states = _normalise_states(validated.get("state"))
            if not states:
                raise InvalidDeviceAutomationConfig("status_is condition requires state")
        elif condition_type in {CONDITION_STATUS_OK, CONDITION_STATUS_RECOVERED}:
            states = set(STATUS_STATES_RECOVERED)
        else:
            states = set(STATUS_STATES_PROBLEM)
    elif condition_type == CONDITION_RUN_ACTIVE:
        if suffix != "run_status":
            raise InvalidDeviceAutomationConfig("run_active condition must target run_status sensor")
        states = {"active", "running"}
    else:  # pragma: no cover - exhaustive guard
        raise InvalidDeviceAutomationConfig(f"unsupported condition type {condition_type}")

    @callback
    def _test_condition(inner_hass: HomeAssistant, _variables: Mapping[str, Any]) -> bool:
        state = inner_hass.states.get(entity_id)
        if state is None:
            return False
        return state.state in states

    return _test_condition


__all__ = [
    "async_get_conditions",
    "async_get_condition_capabilities",
    "async_condition_from_config",
    "CONDITION_STATUS_IS",
    "CONDITION_STATUS_OK",
    "CONDITION_STATUS_PROBLEM",
    "CONDITION_STATUS_RECOVERED",
    "CONDITION_RUN_ACTIVE",
]
