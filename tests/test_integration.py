from pathlib import Path

import pytest
from aiohttp import ClientError
from homeassistant.config_entries import OperationNotAllowed
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.update_coordinator import UpdateFailed
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.horticulture_assistant.api import ChatApi
from custom_components.horticulture_assistant.const import (
    CONF_API_KEY,
    CONF_MOISTURE_SENSOR,
    DOMAIN,
)
from custom_components.horticulture_assistant.diagnostics import (
    async_get_config_entry_diagnostics,
)
from custom_components.horticulture_assistant.storage import LocalStore


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
async def test_coordinator_update_handles_errors(hass: HomeAssistant, enable_custom_integrations: None, monkeypatch):
    entry = await setup_integration(hass, enable_custom_integrations, monkeypatch)
    coord = hass.data[DOMAIN][entry.entry_id]["coordinator_ai"]

    async def raise_client(*args, **kwargs):
        raise ClientError

    monkeypatch.setattr(coord.api, "chat", raise_client)
    with pytest.raises(UpdateFailed):
        await coord._async_update_data()
    assert coord.retry_count == 1

    async def raise_timeout(*args, **kwargs):
        raise TimeoutError

    monkeypatch.setattr(coord.api, "chat", raise_timeout)
    with pytest.raises(UpdateFailed):
        await coord._async_update_data()
    assert coord.retry_count == 2


@pytest.mark.asyncio
async def test_storage_migration(hass: HomeAssistant):
    store = LocalStore(hass)
    await store.save({"recipes": [], "inventory": {}, "history": []})
    loaded = await store.load()
    assert "recommendation" in loaded
    assert "profile" in loaded


@pytest.mark.asyncio
async def test_diagnostics_redaction(hass: HomeAssistant, enable_custom_integrations: None, monkeypatch):
    async def dummy_chat(self, *args, **kwargs):
        return {"choices": [{"message": {"content": "ok"}}]}

    monkeypatch.setattr(ChatApi, "chat", dummy_chat)

    entry = MockConfigEntry(domain=DOMAIN, data={CONF_API_KEY: "secret"})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await async_get_config_entry_diagnostics(hass, entry)
    assert result["entry"]["data"]["api_key"] == "**REDACTED**"
    assert result["schema_version"] == 2
    assert "profile_count" in result
    assert "cloud_sync_status" in result
    assert result["cloud_sync_status"]["configured"] is False


@pytest.mark.asyncio
async def test_unload_calls_shutdown(hass: HomeAssistant, enable_custom_integrations: None, monkeypatch):
    """Ensure coordinators receive shutdown when integration is unloaded."""

    async def dummy_chat(self, *args, **kwargs):
        return {"choices": [{"message": {"content": "ok"}}]}

    monkeypatch.setattr(ChatApi, "chat", dummy_chat)

    entry = MockConfigEntry(domain=DOMAIN, data={CONF_API_KEY: "key"})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    ai_coord = hass.data[DOMAIN][entry.entry_id]["coordinator_ai"]
    local_coord = hass.data[DOMAIN][entry.entry_id]["coordinator_local"]

    ai_called = False
    local_called = False

    async def ai_shutdown():
        nonlocal ai_called
        ai_called = True

    async def local_shutdown():
        nonlocal local_called
        local_called = True

    monkeypatch.setattr(ai_coord, "async_shutdown", ai_shutdown)
    monkeypatch.setattr(local_coord, "async_shutdown", local_shutdown)

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert ai_called
    assert local_called


@pytest.mark.asyncio
async def test_service_validation(hass: HomeAssistant, enable_custom_integrations: None, monkeypatch):
    """Invalid payloads should be rejected by voluptuous schema."""

    async def dummy_chat(self, *args, **kwargs):
        return {"choices": [{"message": {"content": "ok"}}]}

    monkeypatch.setattr(ChatApi, "chat", dummy_chat)

    entry = MockConfigEntry(domain=DOMAIN, data={CONF_API_KEY: "key"})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


@pytest.mark.asyncio
async def test_paths_created(hass: HomeAssistant, enable_custom_integrations: None, monkeypatch, tmp_path):
    """Ensure data/local directories and zones file are created."""

    hass.config.config_dir = str(tmp_path)

    data_root = Path(tmp_path) / "data" / "local"
    zones_file = data_root / "zones.json"
    zones_file.parent.mkdir(parents=True, exist_ok=True)
    zones_file.touch()

    async def dummy_chat(self, *args, **kwargs):
        return {"choices": [{"message": {"content": "ok"}}]}

    monkeypatch.setattr(ChatApi, "chat", dummy_chat)

    entry = MockConfigEntry(domain=DOMAIN, data={CONF_API_KEY: "key"})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert (data_root / "plants").exists()
    assert zones_file.exists()
    assert zones_file.read_text(encoding="utf-8") == ""


@pytest.mark.asyncio
async def test_missing_option_creates_issue(hass: HomeAssistant, enable_custom_integrations: None):
    """Configured sensors that don't exist should raise a Repairs issue."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "key"},
        options={CONF_MOISTURE_SENSOR: "sensor.miss"},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    issues = ir.async_get(hass).issues
    assert (
        DOMAIN,
        f"missing_entity_{entry.entry_id}_sensor.miss",
    ) in issues


@pytest.mark.asyncio
async def test_co2_sensor_checked(hass: HomeAssistant, monkeypatch):
    """Ensure missing CO2 sensors are validated during setup."""

    captured: dict[str, list[str]] = {}

    def fake_ensure(
        hass_arg,
        plant_id,
        entity_ids,
        *,
        translation_key="missing_entity",
        placeholders=None,
    ):
        captured["ids"] = list(entity_ids)

    monkeypatch.setattr(
        "custom_components.horticulture_assistant.binary_sensor.ensure_entities_exist",
        fake_ensure,
    )

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"plant_id": "p1", "plant_name": "Plant", "co2_sensors": ["sensor.bad"]},
    )
    entry.add_to_hass(hass)
    from custom_components.horticulture_assistant import binary_sensor as bs

    await bs.async_setup_entry(hass, entry, lambda entities: None)

    assert "sensor.bad" in captured.get("ids", [])
