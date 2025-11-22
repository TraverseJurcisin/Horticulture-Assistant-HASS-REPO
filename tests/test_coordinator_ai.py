import asyncio
from unittest.mock import MagicMock, patch

import pytest
from aiohttp import ClientError
from homeassistant.helpers.entity_registry import async_get
from homeassistant.helpers.update_coordinator import UpdateFailed
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.horticulture_assistant.const import CONF_API_KEY, DOMAIN

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.usefixtures("enable_custom_integrations"),
]


@pytest.fixture(autouse=True)
def _mock_socket():
    with patch("socket.socket") as mock_socket:
        instance = MagicMock()

        def connect(*args, **kwargs):
            if not instance.setblocking.called or instance.setblocking.call_args[0][0] is not False:
                raise ValueError("the socket must be non-blocking")

        instance.connect.side_effect = connect
        mock_socket.return_value = instance
        with patch(
            "socket.create_connection",
            side_effect=ValueError("the socket must be non-blocking"),
        ):
            yield


async def test_coordinator_handles_failures(hass):
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_API_KEY: "key"})
    entry.add_to_hass(hass)
    with patch(
        "custom_components.horticulture_assistant.api.ChatApi.chat",
        return_value={"choices": [{"message": {"content": "hi"}}]},
    ):
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
    assert state.state == "error"
    assert state.attributes["retry_count"] >= 1
    assert state.attributes["breaker_open"] is False
    assert "ClientError" in (state.attributes["last_exception"] or "")
    assert isinstance(state.attributes["latency_ms"], int)

    with patch(
        "custom_components.horticulture_assistant.api.ChatApi.chat",
        side_effect=asyncio.TimeoutError,
    ):
        await coord.async_request_refresh()
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == "error"
    assert state.attributes["retry_count"] >= 2
    assert isinstance(state.attributes["latency_ms"], int)


async def test_circuit_breaker_skips_calls(hass):
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_API_KEY: "key"})
    entry.add_to_hass(hass)
    with patch(
        "custom_components.horticulture_assistant.api.ChatApi.chat",
        return_value={"choices": [{"message": {"content": "hi"}}]},
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    coord = hass.data[DOMAIN][entry.entry_id]["coordinator_ai"]
    with patch(
        "custom_components.horticulture_assistant.api.ChatApi.chat",
        side_effect=Exception("boom"),
    ):
        for _ in range(4):
            with pytest.raises(UpdateFailed):
                await coord._async_update_data()
    assert coord.breaker_open is True
    data_before = coord.data
    with patch("custom_components.horticulture_assistant.api.ChatApi.chat") as mock_chat:
        result = await coord._async_update_data()
    mock_chat.assert_not_called()
    assert result == data_before
    await hass.async_block_till_done()
