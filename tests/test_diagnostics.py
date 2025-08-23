from unittest.mock import patch

import pytest
from homeassistant.components.diagnostics import REDACTED
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.horticulture_assistant.diagnostics import (
    async_get_config_entry_diagnostics,
)


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
    sample_profiles = {
        "plant1": {
            "plant_id": "plant1",
            "display_name": "Plant",
            "last_resolved": "2024-01-01T00:00:00+00:00",
            "variables": {
                "air_temp_min": {
                    "value": 10,
                    "source": "manual",
                    "citations": [{"source": "manual", "title": "note"}],
                }
            },
        }
    }
    with patch(
        "custom_components.horticulture_assistant.diagnostics.async_load_all",
        return_value=sample_profiles,
    ):
        result = await async_get_config_entry_diagnostics(hass, entry)
    assert result["options"]["api_key"] == REDACTED
    assert result["profiles"] == sample_profiles
    assert result["citations_count"] == 1
    assert result["citations_summary"] == {"air_temp_min": 1}
    assert result["last_resolved_utc"] == "2024-01-01T00:00:00+00:00"
