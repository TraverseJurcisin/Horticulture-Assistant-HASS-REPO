import pytest
from homeassistant.components.diagnostics import REDACTED
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.horticulture_assistant.const import DOMAIN
from custom_components.horticulture_assistant.diagnostics import async_get_config_entry_diagnostics


class DummyRegistry:
    def summaries(self):
        return [{"id": "p1"}]


class DummyCoordinator:
    last_update_success = True
    _last_update_success_time = "2024-01-01T00:00:00+00:00"
    update_interval = 0


@pytest.mark.asyncio
async def test_async_get_config_entry_diagnostics(hass):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"foo": "bar"},
        options={"api_key": "secret", "profiles": {"p1": {}}},
    )
    hass.data[DOMAIN] = {
        "profile_registry": DummyRegistry(),
        "coordinator_ai": DummyCoordinator(),
    }

    result = await async_get_config_entry_diagnostics(hass, entry)

    assert result["entry"]["options"]["api_key"] is REDACTED
    assert result["profiles"] == [{"id": "p1"}]
    assert result["coordinators"]["ai"]["last_update_success"] is True
    assert result["options_profiles"] == ["p1"]
