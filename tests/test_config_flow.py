import pytest
from unittest.mock import MagicMock, patch

from custom_components.horticulture_assistant.const import DOMAIN, CONF_API_KEY
from pytest_homeassistant_custom_component.common import MockConfigEntry
from homeassistant import config_entries

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.usefixtures("enable_custom_integrations"),
]


@pytest.fixture(autouse=True)
def _mock_socket():
    with patch("socket.socket") as mock_socket:
        instance = MagicMock()

        def setblocking(flag):
            if flag is False:
                raise ValueError("the socket must be non-blocking")

        instance.setblocking.side_effect = setblocking
        mock_socket.return_value = instance
        with patch(
            "socket.create_connection",
            side_effect=ValueError("the socket must be non-blocking"),
        ):
            yield

async def test_config_flow_user(hass):
    """Test user config flow."""
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
    await hass.async_block_till_done()


async def test_config_flow_invalid_key(hass):
    """Test config flow handles invalid API key."""
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
    await hass.async_block_till_done()

async def test_options_flow(hass, hass_admin_user):
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_API_KEY: "key"}, title="title")
    entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == "form"
    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"], {}
    )
    assert result2["type"] == "create_entry"
    await hass.async_block_till_done()


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
    await hass.async_block_till_done()


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
    await hass.async_block_till_done()
