import pytest
from custom_components.horticulture_assistant.const import DOMAIN, CONF_API_KEY
from pytest_homeassistant_custom_component.common import MockConfigEntry
from homeassistant.helpers import issue_registry as ir

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.usefixtures("enable_custom_integrations"),
]

async def test_update_sensors_service(hass):
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_API_KEY: "key"}, title="title")
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    await hass.services.async_call(
        DOMAIN,
        "update_sensors",
        {"plant_id": "plant1", "sensors": {"moisture_sensors": ["sensor.miss"]}},
        blocking=True,
    )
    issues = ir.async_get(hass).issues
    assert any(
        issue_id.startswith("missing_entity")
        for (_, issue_id) in issues
    )
    hass.states.async_set("sensor.good", 1)
    await hass.services.async_call(
        DOMAIN,
        "update_sensors",
        {"plant_id": "plant1", "sensors": {"moisture_sensors": ["sensor.good"]}},
        blocking=True,
    )
    store = hass.data[DOMAIN][entry.entry_id]["store"]
    assert store.data["plants"]["plant1"]["sensors"]["moisture_sensors"] == ["sensor.good"]
