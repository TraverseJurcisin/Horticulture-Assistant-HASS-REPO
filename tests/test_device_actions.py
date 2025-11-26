import importlib
import pathlib
import sys
import types

import pytest

try:
    from pytest_homeassistant_custom_component.common import MockConfigEntry
except Exception:  # pragma: no cover
    MockConfigEntry = None

if MockConfigEntry is None:
    pkg = types.ModuleType("custom_components.horticulture_assistant")
    pkg.__path__ = [str(pathlib.Path(__file__).resolve().parents[1] / "custom_components" / "horticulture_assistant")]
    sys.modules.setdefault("custom_components.horticulture_assistant", pkg)

const = importlib.import_module("custom_components.horticulture_assistant.const")
services = importlib.import_module("custom_components.horticulture_assistant.services")
device_action = importlib.import_module("custom_components.horticulture_assistant.device_action")

dr = None
if MockConfigEntry is not None:
    try:
        from homeassistant.helpers import device_registry as dr  # type: ignore[assignment]
    except Exception:
        dr = None

pytestmark = pytest.mark.skipif(
    MockConfigEntry is None or dr is None, reason="pytest-homeassistant-custom-component not installed"
)


@pytest.mark.asyncio
async def test_device_actions_listed(hass):
    device_registry = dr.async_get(hass)

    device = device_registry.async_get_or_create(
        config_entry_id="entry1",
        identifiers={(const.DOMAIN, "profile:avocado")},
        name="Avocado",
    )

    actions = await device_action.async_get_actions(hass, device.id)
    action_types = {action["type"] for action in actions}

    assert device_action.ACTION_REPLACE_SENSORS in action_types


@pytest.mark.asyncio
async def test_replace_sensors_action_calls_service(hass):
    device_registry = dr.async_get(hass)

    device = device_registry.async_get_or_create(
        config_entry_id="entry1",
        identifiers={(const.DOMAIN, "palm")},
        name="Palm",
    )

    calls: list = []

    async def _handle(call):
        calls.append(call)

    hass.services.async_register(const.DOMAIN, services.SERVICE_REPLACE_SENSOR, _handle)

    base_config = next(
        action
        for action in await device_action.async_get_actions(hass, device.id)
        if action["type"] == device_action.ACTION_REPLACE_SENSORS
    )

    await device_action.async_call_action(
        hass,
        {
            **base_config,
            "measurement": "temperature",
            "entity_id": "sensor.palm_temperature",
        },
        {},
        None,
    )

    assert len(calls) == 1
    assert calls[0].data["profile_id"] == "palm"
    assert calls[0].data["measurement"] == "temperature"
    assert calls[0].data["entity_id"] == "sensor.palm_temperature"
