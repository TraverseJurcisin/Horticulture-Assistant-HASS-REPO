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
    pkg.__path__ = [
        str(pathlib.Path(__file__).resolve().parents[1] / "custom_components" / "horticulture_assistant")
    ]
    sys.modules.setdefault("custom_components.horticulture_assistant", pkg)

const = importlib.import_module("custom_components.horticulture_assistant.const")
conditions = importlib.import_module("custom_components.horticulture_assistant.device_condition")

pytestmark = pytest.mark.skipif(
    MockConfigEntry is None, reason="pytest-homeassistant-custom-component not installed"
)

if MockConfigEntry is not None:
    from homeassistant.helpers import device_registry as dr
    from homeassistant.helpers import entity_registry as er


@pytest.mark.asyncio
async def test_conditions_listed(hass):
    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)

    device = device_registry.async_get_or_create(
        config_entry_id="entry1",
        identifiers={(const.DOMAIN, "profile:pineapple")},
        name="Pineapple",
    )
    status_entity = entity_registry.async_get_or_create(
        "sensor",
        const.DOMAIN,
        "pineapple:status",
        suggested_object_id="pineapple_status",
        config_entry_id="entry1",
        device_id=device.id,
    )
    entity_registry.async_get_or_create(
        "sensor",
        const.DOMAIN,
        "pineapple:run_status",
        suggested_object_id="pineapple_run_status",
        config_entry_id="entry1",
        device_id=device.id,
    )

    hass.states.async_set(status_entity.entity_id, const.STATUS_OK)

    condition_types = {
        condition["type"]
        for condition in await conditions.async_get_conditions(hass, device.id)
    }
    assert conditions.CONDITION_STATUS_IS in condition_types
    assert conditions.CONDITION_STATUS_OK in condition_types
    assert conditions.CONDITION_STATUS_PROBLEM in condition_types
    assert conditions.CONDITION_STATUS_RECOVERED in condition_types
    assert conditions.CONDITION_RUN_ACTIVE in condition_types


@pytest.mark.asyncio
async def test_status_problem_condition(hass):
    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)

    device = device_registry.async_get_or_create(
        config_entry_id="entry1",
        identifiers={(const.DOMAIN, "profile:mint")},
        name="Mint",
    )
    status_entity = entity_registry.async_get_or_create(
        "sensor",
        const.DOMAIN,
        "mint:status",
        suggested_object_id="mint_status",
        config_entry_id="entry1",
        device_id=device.id,
    )

    hass.states.async_set(status_entity.entity_id, const.STATUS_WARN)

    base = next(
        cond
        for cond in await conditions.async_get_conditions(hass, device.id)
        if cond["type"] == conditions.CONDITION_STATUS_PROBLEM
    )
    checker = await conditions.async_condition_from_config(hass, base)
    assert checker(hass, {})

    hass.states.async_set(status_entity.entity_id, const.STATUS_OK)
    assert not checker(hass, {})


@pytest.mark.asyncio
async def test_status_is_condition_requires_value(hass):
    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)

    device = device_registry.async_get_or_create(
        config_entry_id="entry2",
        identifiers={(const.DOMAIN, "profile:parsley")},
        name="Parsley",
    )
    status_entity = entity_registry.async_get_or_create(
        "sensor",
        const.DOMAIN,
        "parsley:status",
        suggested_object_id="parsley_status",
        config_entry_id="entry2",
        device_id=device.id,
    )
    hass.states.async_set(status_entity.entity_id, "critical")

    base = next(
        cond
        for cond in await conditions.async_get_conditions(hass, device.id)
        if cond["type"] == conditions.CONDITION_STATUS_IS
    )
    base["state"] = "critical"
    checker = await conditions.async_condition_from_config(hass, base)
    assert checker(hass, {})


@pytest.mark.asyncio
async def test_run_active_condition(hass):
    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)

    device = device_registry.async_get_or_create(
        config_entry_id="entry3",
        identifiers={(const.DOMAIN, "profile:orchard")},
        name="Orchard",
    )
    run_entity = entity_registry.async_get_or_create(
        "sensor",
        const.DOMAIN,
        "orchard:run_status",
        suggested_object_id="orchard_run_status",
        config_entry_id="entry3",
        device_id=device.id,
    )

    hass.states.async_set(run_entity.entity_id, "idle")

    base = next(
        cond
        for cond in await conditions.async_get_conditions(hass, device.id)
        if cond["type"] == conditions.CONDITION_RUN_ACTIVE
    )
    checker = await conditions.async_condition_from_config(hass, base)
    assert not checker(hass, {})

    hass.states.async_set(run_entity.entity_id, "active")
    assert checker(hass, {})
