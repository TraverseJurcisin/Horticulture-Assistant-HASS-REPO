import pytest

try:
    from pytest_homeassistant_custom_component.common import MockConfigEntry
except ModuleNotFoundError:  # pragma: no cover - optional dependency missing
    MockConfigEntry = None

from custom_components.horticulture_assistant import async_migrate_entry
from custom_components.horticulture_assistant.const import (
    CONF_API_KEY,
    CONF_KEEP_STALE,
    CONF_UPDATE_INTERVAL,
    DEFAULT_KEEP_STALE,
    DOMAIN,
)

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.usefixtures("enable_custom_integrations"),
]

if MockConfigEntry is None:  # pragma: no cover - executed when optional dependency missing
    pytestmark.append(pytest.mark.skip(reason="pytest-homeassistant-custom-component not installed"))


async def test_async_migrate_entry_moves_defaults(hass):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "key", CONF_UPDATE_INTERVAL: 15},
        version=1,
    )
    entry.add_to_hass(hass)
    assert await async_migrate_entry(hass, entry)
    assert entry.version == 3
    assert entry.options[CONF_UPDATE_INTERVAL] == 15
    assert entry.options[CONF_KEEP_STALE] == DEFAULT_KEEP_STALE
    assert CONF_UPDATE_INTERVAL not in entry.data
    assert CONF_KEEP_STALE not in entry.data
