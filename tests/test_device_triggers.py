import copy
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
device_trigger = importlib.import_module("custom_components.horticulture_assistant.device_trigger")

DOMAIN = const.DOMAIN

pytestmark = pytest.mark.skipif(MockConfigEntry is None, reason="pytest-homeassistant-custom-component not installed")

if MockConfigEntry is not None:
    from homeassistant.helpers import device_registry as dr
    from homeassistant.helpers import entity_registry as er


@pytest.mark.asyncio
async def test_device_triggers_listed(hass):
    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)

    device = device_registry.async_get_or_create(
        config_entry_id="entry1",
        identifiers={(DOMAIN, "profile:avocado")},
        name="Avocado",
    )
    entity = entity_registry.async_get_or_create(
        "sensor",
        DOMAIN,
        "avocado:status",
        suggested_object_id="avocado_status",
        config_entry_id="entry1",
        device_id=device.id,
    )
    hass.states.async_set(entity.entity_id, "ok")

    triggers = await device_trigger.async_get_triggers(hass, device.id)
    trigger_types = {trigger["type"] for trigger in triggers}
    assert device_trigger.TRIGGER_STATUS_PROBLEM in trigger_types
    assert device_trigger.TRIGGER_STATUS_RECOVERED in trigger_types
    assert device_trigger.TRIGGER_STATUS_CHANGED in trigger_types


@pytest.mark.asyncio
async def test_status_problem_trigger_fires(hass):
    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)

    device = device_registry.async_get_or_create(
        config_entry_id="entry1",
        identifiers={(DOMAIN, "profile:orchid")},
        name="Orchid",
    )
    entity = entity_registry.async_get_or_create(
        "sensor",
        DOMAIN,
        "orchid:status",
        suggested_object_id="orchid_status",
        config_entry_id="entry1",
        device_id=device.id,
    )
    hass.states.async_set(entity.entity_id, "ok")

    trigger_config = next(
        trig
        for trig in await device_trigger.async_get_triggers(hass, device.id)
        if trig["type"] == device_trigger.TRIGGER_STATUS_PROBLEM
    )

    calls: list[dict] = []

    async def action(trigger, variables, context):
        calls.append(trigger)

    remove = await device_trigger.async_attach_trigger(
        hass,
        trigger_config,
        action,
        {"platform": "device"},
    )

    hass.states.async_set(entity.entity_id, "warn")
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0]["to_state"].state == "warn"
    remove()


@pytest.mark.asyncio
async def test_status_changed_trigger_filters(hass):
    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)

    device = device_registry.async_get_or_create(
        config_entry_id="entry1",
        identifiers={(DOMAIN, "profile:lettuce")},
        name="Lettuce",
    )
    entity = entity_registry.async_get_or_create(
        "sensor",
        DOMAIN,
        "lettuce:status",
        suggested_object_id="lettuce_status",
        config_entry_id="entry1",
        device_id=device.id,
    )
    hass.states.async_set(entity.entity_id, "ok")

    base_trigger = next(
        trig
        for trig in await device_trigger.async_get_triggers(hass, device.id)
        if trig["type"] == device_trigger.TRIGGER_STATUS_CHANGED
    )
    trigger_config = copy.deepcopy(base_trigger)
    trigger_config["to"] = "critical"

    calls: list[dict] = []

    async def action(trigger, variables, context):
        calls.append(trigger)

    remove = await device_trigger.async_attach_trigger(
        hass,
        trigger_config,
        action,
        {"platform": "device"},
    )

    hass.states.async_set(entity.entity_id, "warn")
    await hass.async_block_till_done()
    assert not calls
    hass.states.async_set(entity.entity_id, "critical")
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0]["to_state"].state == "critical"
    remove()
