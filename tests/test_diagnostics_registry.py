import pytest

from custom_components.horticulture_assistant.const import CONF_PROFILES, DOMAIN
from custom_components.horticulture_assistant.diagnostics import (
    async_get_config_entry_diagnostics,
)
from custom_components.horticulture_assistant.profile_registry import ProfileRegistry
from pytest_homeassistant_custom_component.common import MockConfigEntry

pytestmark = pytest.mark.asyncio


async def test_diagnostics_uses_registry(hass):
    """Diagnostics should summarize data from the profile registry."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        options={CONF_PROFILES: {"p1": {"name": "Plant"}}},
    )
    entry.add_to_hass(hass)
    reg = ProfileRegistry(hass, entry)
    await reg.async_load()
    hass.data.setdefault(DOMAIN, {})["registry"] = reg

    result = await async_get_config_entry_diagnostics(hass, entry)

    assert result["profile_count"] == 1
    profile = result["profiles"][0]
    assert profile["plant_id"] == "p1"
    assert profile["device_identifier"]["domain"] == DOMAIN
    assert profile["summary"]["device_info"]["identifiers"][0][0] == DOMAIN
