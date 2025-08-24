import pytest
import voluptuous as vol
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.horticulture_assistant.const import CONF_API_KEY, DOMAIN

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


async def test_apply_irrigation_plan_auto_prefers_irrigation_unlimited(hass):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "k", "plant_id": "p1", "plant_name": "Plant"},
        options={"sensors": {"smart_irrigation": "sensor.runtime"}},
    )
    entry.add_to_hass(hass)
    hass.states.async_set("sensor.runtime", 15)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    calls_iu: list = []
    calls_os: list = []

    async def fake_iu(call):
        calls_iu.append(call)

    async def fake_os(call):
        calls_os.append(call)

    hass.services.async_register("irrigation_unlimited", "run_zone", fake_iu)
    hass.services.async_register("opensprinkler", "run_once", fake_os)

    await hass.services.async_call(
        DOMAIN,
        "apply_irrigation_plan",
        {"profile_id": "p1", "provider": "auto", "zone": "z1"},
        blocking=True,
    )

    assert calls_iu and not calls_os
    assert calls_iu[0].data["time"] == 15.0


async def test_apply_irrigation_plan_auto_uses_opensprinkler(hass):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "k", "plant_id": "p1", "plant_name": "Plant"},
        options={"sensors": {"smart_irrigation": "sensor.runtime"}},
    )
    entry.add_to_hass(hass)
    hass.states.async_set("sensor.runtime", 20)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    calls: list = []

    async def fake_os(call):
        calls.append(call)

    hass.services.async_register("opensprinkler", "run_once", fake_os)

    await hass.services.async_call(
        DOMAIN,
        "apply_irrigation_plan",
        {"profile_id": "p1", "provider": "auto", "zone": "s1"},
        blocking=True,
    )

    assert calls
    assert calls[0].data["duration"] == 20.0


async def test_apply_irrigation_plan_no_provider_available(hass):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "k", "plant_id": "p1", "plant_name": "Plant"},
        options={"sensors": {"smart_irrigation": "sensor.runtime"}},
    )
    entry.add_to_hass(hass)
    hass.states.async_set("sensor.runtime", 10)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            DOMAIN,
            "apply_irrigation_plan",
            {"profile_id": "p1", "provider": "auto"},
            blocking=True,
        )
