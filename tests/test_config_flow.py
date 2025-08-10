import pytest
from unittest.mock import patch
from custom_components.horticulture_assistant.const import DOMAIN, CONF_API_KEY
from pytest_homeassistant_custom_component.common import MockConfigEntry
from homeassistant import config_entries

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.usefixtures("enable_custom_integrations"),
]

async def test_config_flow_user(hass):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    with patch(
        "custom_components.horticulture_assistant.config_flow.ChatApi.validate_api_key",
        return_value=None,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_API_KEY: "abc"}
        )
    assert result2["type"] == "create_entry"


async def test_config_flow_invalid_key(hass):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    with patch(
        "custom_components.horticulture_assistant.config_flow.ChatApi.validate_api_key",
        side_effect=Exception,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_API_KEY: "bad"}
        )
    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "cannot_connect"}

async def test_options_flow(hass, hass_admin_user):
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_API_KEY: "key"}, title="title")
    entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == "form"
    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"], {}
    )
    assert result2["type"] == "create_entry"


async def test_options_flow_invalid_entity(hass, hass_admin_user):
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_API_KEY: "key"}, title="title")
    entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == "form"
    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"], {"moisture_sensor": "sensor.bad"}
    )
    assert result2["type"] == "form"
    assert result2["errors"] == {"moisture_sensor": "not_found"}


async def test_options_flow_invalid_interval(hass, hass_admin_user):
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_API_KEY: "key"}, title="title")
    entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == "form"
    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"], {"update_interval": 0}
    )
    assert result2["type"] == "form"
    assert result2["errors"] == {"update_interval": "invalid_interval"}
