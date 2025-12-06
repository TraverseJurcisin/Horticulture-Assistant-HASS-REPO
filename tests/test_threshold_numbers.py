import pytest
from homeassistant.const import EVENT_CORE_CONFIG_UPDATE, Platform, UnitOfTemperature
from homeassistant.helpers.dispatcher import async_dispatcher_send
from pytest_homeassistant_custom_component.common import MockConfigEntry

import custom_components.horticulture_assistant.number as number
from custom_components.horticulture_assistant.const import (
    CONF_API_KEY,
    DOMAIN,
    signal_profile_contexts_updated,
)
from custom_components.horticulture_assistant.utils.entry_helpers import get_entry_data

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
    target = entry.options["resolved_targets"]["temperature_min"]
    assert target["value"] == 7.0
    assert target["annotation"]["source_type"] == "manual"


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
    target = entry.options["resolved_targets"]["temperature_min"]
    assert pytest.approx(target["value"], rel=1e-3) == 20


async def test_threshold_numbers_include_new_specs_on_update(hass, monkeypatch):
    monkeypatch.setattr(number, "THRESHOLD_SPECS", [("temperature_min", "°C")])

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "k", "plant_id": "p1", "plant_name": "Plant 1"},
        options={"thresholds": {}},
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("number.plant_1_temperature_min") is not None

    monkeypatch.setattr(
        number,
        "THRESHOLD_SPECS",
        [("temperature_min", "°C"), ("humidity_min", "%")],
    )

    async_dispatcher_send(
        hass,
        signal_profile_contexts_updated(entry.entry_id),
        {"added": (), "removed": (), "updated": ("p1",)},
    )
    await hass.async_block_till_done()

    new_state = hass.states.get("number.plant_1_humidity_min")
    assert new_state is not None
    assert new_state.state == "unknown"


async def test_threshold_numbers_created_for_added_profile(hass):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "k", "plant_id": "p1", "plant_name": "Plant 1"},
        options={"thresholds": {}},
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    entry_data = get_entry_data(hass, entry)
    profile_contexts = dict(entry_data.get("profile_contexts", {}))
    profile_contexts["p2"] = {"name": "Plant 2", "thresholds": {}}
    entry_data["profile_contexts"] = profile_contexts

    async_dispatcher_send(
        hass,
        signal_profile_contexts_updated(entry.entry_id),
        {"added": ("p2",), "removed": (), "updated": ()},
    )
    await hass.async_block_till_done()

    assert hass.states.get("number.plant_2_temperature_min") is not None


async def test_threshold_numbers_reconciled_when_change_empty(hass, monkeypatch):
    monkeypatch.setattr(number, "THRESHOLD_SPECS", [("temperature_min", "°C")])

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "k", "plant_id": "p1", "plant_name": "Plant 1"},
        options={"thresholds": {}},
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("number.plant_1_temperature_min") is not None

    monkeypatch.setattr(number, "THRESHOLD_SPECS", [("temperature_min", "°C"), ("humidity_min", "%")])

    async_dispatcher_send(
        hass,
        signal_profile_contexts_updated(entry.entry_id),
        {"added": (), "removed": (), "updated": ()},
    )
    await hass.async_block_till_done()

    assert hass.states.get("number.plant_1_humidity_min") is not None
