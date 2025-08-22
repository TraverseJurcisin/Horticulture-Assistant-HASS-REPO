import pytest
from unittest.mock import patch
from homeassistant.components.diagnostics import REDACTED
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.horticulture_assistant.diagnostics import async_get_config_entry_diagnostics


class _States:
    def async_all(self):
        return []


@pytest.mark.asyncio
async def test_async_get_config_entry_diagnostics(hass):
    hass.states = _States()
    entry = MockConfigEntry(
        domain="horticulture_assistant",
        data={"foo": "bar"},
        options={"api_key": "secret"},
    )
    sample_profiles = {"plant1": {"plant_id": "plant1", "display_name": "Plant"}}
    with patch(
        "custom_components.horticulture_assistant.diagnostics.async_load_all",
        return_value=sample_profiles,
    ):
        result = await async_get_config_entry_diagnostics(hass, entry)
    assert result["options"]["api_key"] == REDACTED
    assert result["profiles"] == sample_profiles
