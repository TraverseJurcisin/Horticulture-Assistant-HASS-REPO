import pytest
from homeassistant.helpers import issue_registry as ir

from custom_components.horticulture_assistant.const import (
    CONF_API_KEY,
    CONF_MOISTURE_SENSOR,
    DOMAIN,
)
from pytest_homeassistant_custom_component.common import MockConfigEntry

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.usefixtures("enable_custom_integrations"),
]


async def test_missing_option_entity_creates_issue(hass):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "key"},
        options={CONF_MOISTURE_SENSOR: "sensor.missing"},
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    issues = ir.async_get(hass).issues
    assert (DOMAIN, f"missing_entity_{entry.entry_id}_sensor.missing") in issues
