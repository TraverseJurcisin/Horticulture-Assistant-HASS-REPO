import pytest
import voluptuous as vol
from unittest.mock import AsyncMock
from custom_components.horticulture_assistant.const import DOMAIN, CONF_API_KEY
from pytest_homeassistant_custom_component.common import MockConfigEntry
from homeassistant.helpers import issue_registry as ir

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.usefixtures("enable_custom_integrations"),
]


async def test_update_sensors_service(hass):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "key", "plant_id": "plant1", "plant_name": "Plant 1"},
        title="Plant 1",
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            DOMAIN,
            "update_sensors",
            {"plant_id": "plant1", "sensors": {"moisture_sensors": "sensor.miss"}},
            blocking=True,
        )
    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            DOMAIN,
            "update_sensors",
            {"plant_id": "plant1", "sensors": {"moisture_sensors": ["sensor.miss"]}},
            blocking=True,
        )
    issues = ir.async_get(hass).issues
    assert any(issue_id.startswith("missing_entity") for (_, issue_id) in issues)
    hass.states.async_set("sensor.good", 1)
    await hass.services.async_call(
        DOMAIN,
        "update_sensors",
        {"plant_id": "plant1", "sensors": {"moisture_sensors": ["sensor.good"]}},
        blocking=True,
    )
    store = hass.data[DOMAIN][entry.entry_id]["store"]
    assert store.data["plants"]["plant1"]["sensors"]["moisture_sensors"] == [
        "sensor.good"
    ]


async def test_replace_sensor_service(hass):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "key", "plant_id": "plant1", "plant_name": "Plant 1"},
        title="Plant 1",
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            DOMAIN,
            "replace_sensor",
            {"plant_id": "plant1", "role": "moisture", "new_sensor": "sensor.bad"},
            blocking=True,
        )
    hass.states.async_set("sensor.good", 2)
    await hass.services.async_call(
        DOMAIN,
        "replace_sensor",
        {"plant_id": "plant1", "role": "moisture", "new_sensor": "sensor.good"},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert entry.options["sensors"]["moisture"] == "sensor.good"


async def test_refresh_service(hass):
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_API_KEY: "key"})
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    ai = hass.data[DOMAIN][entry.entry_id]["coordinator_ai"]
    local = hass.data[DOMAIN][entry.entry_id]["coordinator_local"]
    ai.async_request_refresh = AsyncMock(wraps=ai.async_request_refresh)
    local.async_request_refresh = AsyncMock(wraps=local.async_request_refresh)
    with pytest.raises(vol.Invalid):
        await hass.services.async_call(DOMAIN, "refresh", {"bad": 1}, blocking=True)
    await hass.services.async_call(DOMAIN, "refresh", {}, blocking=True)
    assert ai.async_request_refresh.called
    assert local.async_request_refresh.called


async def test_recalculate_and_run_recommendation_services(hass):
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_API_KEY: "key"})
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    store = hass.data[DOMAIN][entry.entry_id]["store"]
    ai = hass.data[DOMAIN][entry.entry_id]["coordinator_ai"]
    local = hass.data[DOMAIN][entry.entry_id]["coordinator_local"]

    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            DOMAIN, "recalculate_targets", {"plant_id": "p1"}, blocking=True
        )

    store.data.setdefault("plants", {})["p1"] = {}
    local.async_request_refresh = AsyncMock(wraps=local.async_request_refresh)
    await hass.services.async_call(
        DOMAIN, "recalculate_targets", {"plant_id": "p1"}, blocking=True
    )
    assert local.async_request_refresh.called

    ai.async_request_refresh = AsyncMock(wraps=ai.async_request_refresh)
    ai.data = {"recommendation": "water"}
    await hass.services.async_call(
        DOMAIN,
        "run_recommendation",
        {"plant_id": "p1", "approve": True},
        blocking=True,
    )
    assert ai.async_request_refresh.called
    assert store.data["plants"]["p1"]["recommendation"] == "water"
