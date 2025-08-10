import asyncio
from aiohttp import ClientError
import pytest
from unittest.mock import patch
from custom_components.horticulture_assistant.const import DOMAIN, CONF_API_KEY
from homeassistant.helpers.entity_registry import async_get
from pytest_homeassistant_custom_component.common import MockConfigEntry

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.usefixtures("enable_custom_integrations"),
]


async def test_coordinator_handles_failures(hass):
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_API_KEY: "key"})
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    coord = hass.data[DOMAIN][entry.entry_id]["coordinator_ai"]
    with patch(
        "custom_components.horticulture_assistant.api.ChatApi.chat",
        side_effect=ClientError,
    ):
        await coord.async_request_refresh()
    await hass.async_block_till_done()
    reg = async_get(hass)
    entity_id = reg.async_get_entity_id("sensor", DOMAIN, f"{DOMAIN}_{entry.entry_id}_status")
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state in ("ok", "error")
    assert state.attributes["retry_count"] >= 1
    assert state.attributes["breaker_open"] is False

    with patch(
        "custom_components.horticulture_assistant.api.ChatApi.chat",
        side_effect=asyncio.TimeoutError,
    ):
        await coord.async_request_refresh()
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.attributes["retry_count"] >= 2
