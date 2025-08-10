import asyncio
import pytest
from aiohttp import ClientError
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed
from homeassistant.config_entries import OperationNotAllowed
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.horticulture_assistant.const import DOMAIN, CONF_API_KEY
from custom_components.horticulture_assistant.diagnostics import async_get_config_entry_diagnostics
from custom_components.horticulture_assistant.storage import LocalStore
from custom_components.horticulture_assistant.api import ChatApi


async def setup_integration(hass: HomeAssistant, enable_custom_integrations: None, monkeypatch):
    async def dummy_chat(self, *args, **kwargs):
        return {"choices": [{"message": {"content": "ok"}}]}

    monkeypatch.setattr(ChatApi, "chat", dummy_chat)

    entry = MockConfigEntry(domain=DOMAIN, data={CONF_API_KEY: "key"})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


@pytest.mark.asyncio
async def test_setup_unload_idempotent(hass: HomeAssistant, enable_custom_integrations: None, monkeypatch):
    async def dummy_chat(self, *args, **kwargs):
        return {"choices": [{"message": {"content": "ok"}}]}

    monkeypatch.setattr(ChatApi, "chat", dummy_chat)

    entry = MockConfigEntry(domain=DOMAIN, data={CONF_API_KEY: "key"})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    with pytest.raises(OperationNotAllowed):
        await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


@pytest.mark.asyncio
async def test_coordinator_update_failed(hass: HomeAssistant, enable_custom_integrations: None, monkeypatch):
    entry = await setup_integration(hass, enable_custom_integrations, monkeypatch)
    coord = hass.data[DOMAIN][entry.entry_id]["coordinator_ai"]

    async def raise_client(*args, **kwargs):
        raise ClientError

    monkeypatch.setattr(coord.api, "chat", raise_client)
    with pytest.raises(UpdateFailed):
        await coord._async_update_data()

    async def raise_timeout(*args, **kwargs):
        raise asyncio.TimeoutError

    monkeypatch.setattr(coord.api, "chat", raise_timeout)
    with pytest.raises(UpdateFailed):
        await coord._async_update_data()


@pytest.mark.asyncio
async def test_storage_migration(hass: HomeAssistant):
    store = LocalStore(hass)
    await store.save({"recipes": [], "inventory": {}, "history": []})
    loaded = await store.load()
    assert "recommendation" in loaded
    assert "profile" in loaded


@pytest.mark.asyncio
async def test_diagnostics_redaction(
    hass: HomeAssistant, enable_custom_integrations: None, monkeypatch
):
    async def dummy_chat(self, *args, **kwargs):
        return {"choices": [{"message": {"content": "ok"}}]}

    monkeypatch.setattr(ChatApi, "chat", dummy_chat)

    entry = MockConfigEntry(domain=DOMAIN, data={CONF_API_KEY: "secret"})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await async_get_config_entry_diagnostics(hass, entry)
    assert result["data"]["api_key"] == "**REDACTED**"
    assert result["ai_retry_count"] == 0
    assert result["ai_breaker_open"] is False
    assert "ai_latency_ms" in result
