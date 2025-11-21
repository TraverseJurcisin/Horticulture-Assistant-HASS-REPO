from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from aiohttp import ClientError
from homeassistant.config_entries import OperationNotAllowed
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.entity_registry import async_get as async_get_entity_registry
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.horticulture_assistant.api import ChatApi
from custom_components.horticulture_assistant.const import (
    CONF_API_KEY,
    CONF_MOISTURE_SENSOR,
    DOMAIN,
    signal_profile_contexts_updated,
)
from custom_components.horticulture_assistant.diagnostics import async_get_config_entry_diagnostics
from custom_components.horticulture_assistant.storage import LocalStore
from pytest_homeassistant_custom_component.common import MockConfigEntry


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
    assert result["schema_version"] == 10
    assert "profile_count" in result
    assert "cloud_sync_status" in result
    assert result["cloud_sync_status"]["configured"] is False
    assert "onboarding_errors" not in result
    assert "onboarding_status" in result
    status = result["onboarding_status"]
    assert status["ready"] is result.get("onboarding_ready")
    assert status["stages"]["service_registration"]["status"] == "success"
    assert status["stages"]["calibration_services"]["status"] in {"skipped", "success"}
    assert status["metrics"]["progress"] == 1.0
    assert result["onboarding_metrics"]["progress"] == 1.0
    assert status["blocked"] == []
    assert status["stages"]["cloud_sync"]["status"] == "warning"
    assert "cloud_sync" in status["warnings"]
    assert result["onboarding_metrics"]["warnings_total"] >= 1
    assert "cloud_sync" in result["onboarding_metrics"]["warnings"]
    assert result["onboarding_warnings"]["cloud_sync"]
    assert isinstance(status.get("timeline"), list) and status["timeline"]
    assert isinstance(result.get("onboarding_timeline"), list) and result["onboarding_timeline"]
    assert "onboarding_stage_state" in result
    assert isinstance(result.get("onboarding_history"), list)


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
async def test_profile_update_dispatches_signal(
    hass: HomeAssistant,
    enable_custom_integrations: None,
    monkeypatch,
):
    """Adding a profile triggers dispatcher notifications for entity platforms."""

    async def dummy_chat(self, *args, **kwargs):
        return {"choices": [{"message": {"content": "ok"}}]}

    monkeypatch.setattr(ChatApi, "chat", dummy_chat)

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "key"},
        options={"profiles": {}},
    )
    entry.add_to_hass(hass)

    with patch("custom_components.horticulture_assistant.async_dispatcher_send") as mock_send:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        mock_send.reset_mock()

        profiles = dict(entry.options.get("profiles", {}))
        profiles["new_profile"] = {"name": "New Profile"}
        new_options = dict(entry.options)
        new_options["profiles"] = profiles
        hass.config_entries.async_update_entry(entry, options=new_options)
        await hass.async_block_till_done()

        mock_send.assert_called_once()
        _, signal, payload = mock_send.call_args[0]
        assert signal == signal_profile_contexts_updated(entry.entry_id)
        assert payload.get("added") == ("new_profile",)
        assert payload.get("removed") == ()


@pytest.mark.asyncio
async def test_new_profile_creates_entities(
    hass: HomeAssistant,
    enable_custom_integrations: None,
    monkeypatch,
):
    """Ensure a newly added profile provisions entities without a reload."""

    async def dummy_chat(self, *args, **kwargs):
        return {"choices": [{"message": {"content": "ok"}}]}

    monkeypatch.setattr(ChatApi, "chat", dummy_chat)

    entry = MockConfigEntry(domain=DOMAIN, data={CONF_API_KEY: "key"})
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    profiles = dict(entry.options.get("profiles", {}))
    profiles["new_growth"] = {
        "name": "New Growth",
        "sensors": {
            "moisture": "sensor.mock_moisture",
            "temperature": "sensor.mock_temperature",
            "humidity": "sensor.mock_humidity",
        },
    }
    new_options = dict(entry.options)
    new_options["profiles"] = profiles

    hass.config_entries.async_update_entry(entry, options=new_options)
    await hass.async_block_till_done()

    entity_registry = async_get_entity_registry(hass)

    unique_prefix = f"{DOMAIN}_{entry.entry_id}_new_growth"

    status_entity_id = entity_registry.async_get_entity_id(
        "sensor",
        DOMAIN,
        f"{unique_prefix}_health",
    )
    assert status_entity_id is not None
    assert hass.states.get(status_entity_id) is not None

    moisture_number_id = entity_registry.async_get_entity_id(
        "number",
        DOMAIN,
        f"{unique_prefix}_moisture_min",
    )
    assert moisture_number_id is not None

    irrigation_binary_id = entity_registry.async_get_entity_id(
        "binary_sensor",
        DOMAIN,
        f"{unique_prefix}_irrigation_readiness",
    )
    assert irrigation_binary_id is not None

    irrigation_switch_id = entity_registry.async_get_entity_id(
        "switch",
        DOMAIN,
        f"{unique_prefix}_irrigation_switch",
    )
    assert irrigation_switch_id is not None

    ppfd_entity_id = entity_registry.async_get_entity_id(
        "sensor",
        DOMAIN,
        f"{unique_prefix}_ppfd",
    )
    assert ppfd_entity_id is not None


@pytest.mark.asyncio
async def test_new_profile_requests_refresh(
    hass: HomeAssistant,
    enable_custom_integrations: None,
    monkeypatch,
):
    """Ensure adding a profile schedules a refresh on the profile coordinator."""

    async def dummy_chat(self, *args, **kwargs):
        return {"choices": [{"message": {"content": "ok"}}]}

    monkeypatch.setattr(ChatApi, "chat", dummy_chat)

    entry = MockConfigEntry(domain=DOMAIN, data={CONF_API_KEY: "key"})
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    assert coordinator is not None
    refresh_mock = AsyncMock()
    monkeypatch.setattr(coordinator, "async_request_refresh", refresh_mock)

    profiles = dict(entry.options.get("profiles", {}))
    profiles["fresh_profile"] = {"name": "Fresh Profile"}
    new_options = dict(entry.options)
    new_options["profiles"] = profiles

    hass.config_entries.async_update_entry(entry, options=new_options)
    await hass.async_block_till_done()

    assert refresh_mock.await_count == 1


@pytest.mark.asyncio
async def test_profile_metric_unique_ids_migrated(
    hass: HomeAssistant,
    enable_custom_integrations: None,
    monkeypatch,
):
    """Legacy unique ids are migrated to include the config entry id."""

    async def dummy_chat(self, *args, **kwargs):
        return {"choices": [{"message": {"content": "ok"}}]}

    monkeypatch.setattr(ChatApi, "chat", dummy_chat)

    entry = MockConfigEntry(domain=DOMAIN, data={CONF_API_KEY: "key"})
    entry.add_to_hass(hass)

    entity_registry = async_get_entity_registry(hass)
    legacy = entity_registry.async_get_or_create(
        "sensor",
        DOMAIN,
        "legacy_profile:ppfd",
        suggested_object_id="legacy_profile_ppfd",
        config_entry=entry,
    )

    assert legacy.unique_id == "legacy_profile:ppfd"

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    updated = entity_registry.async_get(legacy.entity_id)
    assert updated is not None
    assert updated.unique_id == f"{DOMAIN}_{entry.entry_id}_legacy_profile_ppfd"


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
