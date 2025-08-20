import pytest
from datetime import datetime

from pytest_homeassistant_custom_component.common import MockConfigEntry
from homeassistant.helpers.entity_registry import async_get
from homeassistant.util import dt as dt_util

from custom_components.horticulture_assistant.const import DOMAIN, CONF_API_KEY

pytestmark = [pytest.mark.asyncio, pytest.mark.usefixtures("enable_custom_integrations")]


async def test_dli_sensor_tracks_light(hass, monkeypatch):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_API_KEY: "k",
            "plant_id": "p1",
            "plant_name": "Plant 1",
        },
        options={"sensors": {"illuminance": "sensor.light1"}},
    )
    entry.add_to_hass(hass)
    hass.states.async_set("sensor.light1", 0)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    unique_id = f"{DOMAIN}_{entry.entry_id}_{entry.data['plant_id']}_dli"
    reg = async_get(hass)
    entity_id = reg.async_get_entity_id("sensor", DOMAIN, unique_id)
    assert entity_id is not None

    # First day accumulation
    monkeypatch.setattr(dt_util, "utcnow", lambda: datetime(2024, 1, 1, tzinfo=dt_util.UTC))
    hass.states.async_set("sensor.light1", 1_000_000)
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "1.11"

    # Next day should reset and accumulate separately
    monkeypatch.setattr(dt_util, "utcnow", lambda: datetime(2024, 1, 2, tzinfo=dt_util.UTC))
    hass.states.async_set("sensor.light1", 1_000_000)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "1.11"
