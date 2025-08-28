import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.horticulture_assistant.const import CONF_PROFILES, DOMAIN
from custom_components.horticulture_assistant.profile_registry import ProfileRegistry

pytestmark = pytest.mark.asyncio


async def test_registry_len_and_iter(hass):
    """Ensure len() and iteration reflect underlying profiles."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        options={CONF_PROFILES: {"p1": {"name": "One"}, "p2": {"name": "Two"}}},
    )
    entry.add_to_hass(hass)
    reg = ProfileRegistry(hass, entry)
    await reg.async_initialize()
    assert len(reg) == 2
    assert {p.plant_id for p in reg} == {"p1", "p2"}


async def test_len_stable_after_sensor_updates(hass):
    entry = MockConfigEntry(
        domain=DOMAIN, data={}, options={CONF_PROFILES: {"p1": {"name": "One"}}}
    )
    entry.add_to_hass(hass)
    reg = ProfileRegistry(hass, entry)
    await reg.async_initialize()
    assert len(reg) == 1
    await reg.async_replace_sensor("p1", "temperature", "sensor.x")
    assert len(reg) == 1
