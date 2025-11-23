import pytest
from homeassistant.const import UnitOfTemperature
from homeassistant.helpers.entity_registry import async_get
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.horticulture_assistant.const import CONF_API_KEY, DOMAIN

pytestmark = [pytest.mark.asyncio, pytest.mark.usefixtures("enable_custom_integrations")]


async def test_initial_values(hass):
    """Sensors should compute values from existing states on setup."""
    hass.states.async_set("sensor.temp1", 25)
    hass.states.async_set("sensor.hum1", 50)

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
    uid_vpd = f"{DOMAIN}_{entry.entry_id}_{entry.data['plant_id']}_vpd"
    uid_dp = f"{DOMAIN}_{entry.entry_id}_{entry.data['plant_id']}_dew_point"
    entity_vpd = reg.async_get_entity_id("sensor", DOMAIN, uid_vpd)
    entity_dp = reg.async_get_entity_id("sensor", DOMAIN, uid_dp)
    state_vpd = hass.states.get(entity_vpd)
    state_dp = hass.states.get(entity_dp)
    assert state_vpd.state == "1.584"
    assert state_dp.state == "13.9"


async def test_vpd_and_dew_point_sensors(hass):
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
    hass.states.async_set("sensor.hum1", 50)
    await hass.async_block_till_done()

    reg = async_get(hass)
    uid_vpd = f"{DOMAIN}_{entry.entry_id}_{entry.data['plant_id']}_vpd"
    uid_dp = f"{DOMAIN}_{entry.entry_id}_{entry.data['plant_id']}_dew_point"
    entity_vpd = reg.async_get_entity_id("sensor", DOMAIN, uid_vpd)
    entity_dp = reg.async_get_entity_id("sensor", DOMAIN, uid_dp)
    assert entity_vpd is not None
    assert entity_dp is not None

    state_vpd = hass.states.get(entity_vpd)
    state_dp = hass.states.get(entity_dp)
    assert state_vpd is not None
    assert state_dp is not None
    assert state_vpd.state == "1.584"
    assert state_dp.state == "13.9"


async def test_vpd_and_dew_point_sensors_fahrenheit(hass):
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

    hass.states.async_set(
        "sensor.temp1",
        77,
        {"unit_of_measurement": UnitOfTemperature.FAHRENHEIT},
    )
    hass.states.async_set("sensor.hum1", 50)
    await hass.async_block_till_done()

    reg = async_get(hass)
    uid_vpd = f"{DOMAIN}_{entry.entry_id}_{entry.data['plant_id']}_vpd"
    uid_dp = f"{DOMAIN}_{entry.entry_id}_{entry.data['plant_id']}_dew_point"
    entity_vpd = reg.async_get_entity_id("sensor", DOMAIN, uid_vpd)
    entity_dp = reg.async_get_entity_id("sensor", DOMAIN, uid_dp)
    assert entity_vpd is not None
    assert entity_dp is not None

    state_vpd = hass.states.get(entity_vpd)
    state_dp = hass.states.get(entity_dp)
    assert state_vpd is not None
    assert state_dp is not None
    assert state_vpd.state == "1.584"
    assert state_dp.state == "13.9"
