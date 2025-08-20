import pytest

from pytest_homeassistant_custom_component.common import MockConfigEntry
from homeassistant.const import Platform, UnitOfTemperature, EVENT_CORE_CONFIG_UPDATE

from custom_components.horticulture_assistant.const import DOMAIN, CONF_API_KEY

pytestmark = [pytest.mark.asyncio, pytest.mark.usefixtures("enable_custom_integrations")]


async def test_threshold_numbers_persist_options(hass):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "k", "plant_id": "p1", "plant_name": "Plant 1"},
        options={"thresholds": {"temperature_min": 5}},
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    entity_id = "number.plant_1_temperature_min"
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "5.0"

    await hass.services.async_call(
        Platform.NUMBER.value,
        "set_value",
        {"entity_id": entity_id, "value": 7},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert entry.options["thresholds"]["temperature_min"] == 7.0


async def test_threshold_numbers_follow_unit_system(hass):
    hass.config.units.temperature_unit = UnitOfTemperature.CELSIUS
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "k", "plant_id": "p1", "plant_name": "Plant 1"},
        options={"thresholds": {"temperature_min": 0}},
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    entity_id = "number.plant_1_temperature_min"
    assert hass.states.get(entity_id).state == "0.0"

    hass.config.units.temperature_unit = UnitOfTemperature.FAHRENHEIT
    hass.bus.async_fire(EVENT_CORE_CONFIG_UPDATE, {})
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == "32.0"

    await hass.services.async_call(
        Platform.NUMBER.value,
        "set_value",
        {"entity_id": entity_id, "value": 68},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert entry.options["thresholds"]["temperature_min"] == pytest.approx(20)
