import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.horticulture_assistant.const import DOMAIN, CONF_API_KEY

pytestmark = [pytest.mark.asyncio, pytest.mark.usefixtures("enable_custom_integrations")]


async def test_apply_irrigation_plan_calls_provider(hass):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "k", "plant_id": "p1", "plant_name": "Plant"},
        options={"sensors": {"smart_irrigation": "sensor.runtime"}},
    )
    entry.add_to_hass(hass)
    hass.states.async_set("sensor.runtime", 30)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    calls: list = []

    async def fake_run(call):
        calls.append(call)

    hass.services.async_register("irrigation_unlimited", "run_zone", fake_run)

    await hass.services.async_call(
        DOMAIN,
        "apply_irrigation_plan",
        {"profile_id": "p1", "provider": "irrigation_unlimited", "zone": "z1"},
        blocking=True,
    )

    assert calls
    assert calls[0].data["time"] == 30.0
