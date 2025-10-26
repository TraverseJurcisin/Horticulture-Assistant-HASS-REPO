import pytest
from homeassistant.helpers.entity_registry import async_get

from custom_components.horticulture_assistant.const import CONF_API_KEY, DOMAIN
from pytest_homeassistant_custom_component.common import MockConfigEntry

pytestmark = [pytest.mark.asyncio, pytest.mark.usefixtures("enable_custom_integrations")]


async def test_initial_mold_risk(hass):
    """Mold risk should compute from existing states on setup."""
    hass.states.async_set("sensor.temp1", 25)
    hass.states.async_set("sensor.hum1", 95)

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_API_KEY: "k",
            "plant_id": "p1",
            "plant_name": "Plant 1",
        },
        options={
            "sensors": {
                "temperature": "sensor.temp1",
                "humidity": "sensor.hum1",
            }
        },
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    reg = async_get(hass)
    uid = f"{DOMAIN}_{entry.entry_id}_{entry.data['plant_id']}_mold_risk"
    entity_id = reg.async_get_entity_id("sensor", DOMAIN, uid)
    state = hass.states.get(entity_id)
    assert state.state == "6.0"


async def test_mold_risk_sensor(hass):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_API_KEY: "k",
            "plant_id": "p1",
            "plant_name": "Plant 1",
        },
        options={
            "sensors": {
                "temperature": "sensor.temp1",
                "humidity": "sensor.hum1",
            }
        },
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    hass.states.async_set("sensor.temp1", 25)
    hass.states.async_set("sensor.hum1", 95)
    await hass.async_block_till_done()

    reg = async_get(hass)
    uid = f"{DOMAIN}_{entry.entry_id}_{entry.data['plant_id']}_mold_risk"
    entity_id = reg.async_get_entity_id("sensor", DOMAIN, uid)
    assert entity_id is not None

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "6.0"
