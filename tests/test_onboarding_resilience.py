import types
from unittest.mock import AsyncMock

import pytest

from custom_components.horticulture_assistant import async_setup_entry
from custom_components.horticulture_assistant.const import DOMAIN
from custom_components.horticulture_assistant.diagnostics import async_get_config_entry_diagnostics
from pytest_homeassistant_custom_component.common import MockConfigEntry


@pytest.mark.asyncio
async def test_onboarding_records_and_clears_stage_errors(hass, enable_custom_integrations, monkeypatch):
    entry = MockConfigEntry(domain=DOMAIN, data={})
    entry.add_to_hass(hass)

    created: list[tuple[str, dict]] = []
    deleted: list[str] = []

    class _Severity:
        ERROR = "error"
        WARNING = "warning"

    monkeypatch.setattr(
        "custom_components.horticulture_assistant.__init__.ir",
        types.SimpleNamespace(
            IssueSeverity=_Severity,
            async_create_issue=lambda *_args, **kwargs: created.append((_args[2], kwargs)),
            async_delete_issue=lambda *_args: deleted.append(_args[2]),
        ),
    )

    monkeypatch.setattr(
        "custom_components.horticulture_assistant.__init__.ensure_local_data_paths",
        AsyncMock(return_value=None),
    )
    dataset_health_mock = AsyncMock(return_value=None)
    monkeypatch.setattr(
        "custom_components.horticulture_assistant.__init__.async_setup_dataset_health",
        dataset_health_mock,
    )
    monkeypatch.setattr(
        "custom_components.horticulture_assistant.__init__.ProfileStore.async_init",
        AsyncMock(side_effect=RuntimeError("library offline")),
    )
    profile_registry_init = AsyncMock(return_value=None)
    monkeypatch.setattr(
        "custom_components.horticulture_assistant.__init__.ProfileRegistry.async_initialize",
        profile_registry_init,
    )
    cloud_start_mock = AsyncMock(return_value=None)
    monkeypatch.setattr(
        "custom_components.horticulture_assistant.__init__.CloudSyncManager.async_start",
        cloud_start_mock,
    )
    register_all_mock = AsyncMock(return_value=None)
    monkeypatch.setattr(
        "custom_components.horticulture_assistant.__init__.ha_services.async_register_all",
        register_all_mock,
    )
    setup_services_mock = AsyncMock(return_value=None)
    monkeypatch.setattr(
        "custom_components.horticulture_assistant.__init__.ha_services.async_setup_services",
        setup_services_mock,
    )
    coordinator_refresh_mock = AsyncMock(return_value=None)
    monkeypatch.setattr(
        "custom_components.horticulture_assistant.__init__.HorticultureCoordinator.async_config_entry_first_refresh",
        coordinator_refresh_mock,
    )
    http_register_mock = AsyncMock(return_value=None)
    monkeypatch.setattr(
        "custom_components.horticulture_assistant.__init__.async_register_http_views",
        http_register_mock,
    )
    monkeypatch.setattr(
        "custom_components.horticulture_assistant.__init__.calibration_services",
        None,
        raising=False,
    )

    assert await async_setup_entry(hass, entry)

    assert dataset_health_mock.await_count == 1
    assert coordinator_refresh_mock.await_count == 0
    assert profile_registry_init.await_count == 0
    assert cloud_start_mock.await_count == 0
    assert register_all_mock.await_count == 0
    assert setup_services_mock.await_count == 0
    assert http_register_mock.await_count == 1

    stored = hass.data[DOMAIN][entry.entry_id]
    assert stored["profile_store_ready"] is False
    errors = stored["onboarding_errors"]
    assert "profile_store" in errors
    assert "library offline" in errors["profile_store"]["error"]
    timeline = stored["onboarding_timeline"]
    assert timeline
    assert any(event["stage"] == "profile_store" and event["status"] == "failed" for event in timeline)
    blocked_event = next(
        event for event in timeline if event["stage"] == "profile_registry" and event["status"] == "blocked"
    )
    assert blocked_event.get("blocked_by") == ["profile_store"]
    status = stored["onboarding_status"]
    assert status["stages"]["profile_store"]["status"] == "failed"
    assert status["stages"]["profile_registry"]["status"] == "blocked"
    assert status["stages"]["profile_registry"].get("blocked_by") == ["profile_store"]
    entity_stage = status["stages"]["entity_validation"]
    assert entity_stage["status"] == "blocked"
    assert entity_stage.get("blocked_by") == ["profile_registry"]
    cloud_stage = status["stages"]["cloud_sync"]
    assert cloud_stage["status"] == "blocked"
    assert cloud_stage.get("blocked_by") == ["profile_registry"]
    service_stage = status["stages"]["service_registration"]
    assert service_stage["status"] == "blocked"
    assert service_stage.get("blocked_by") == ["profile_registry"]
    calibration_stage = status["stages"]["calibration_services"]
    assert calibration_stage["status"] == "blocked"
    assert calibration_stage.get("blocked_by") == ["service_registration"]
    platform_stage = status["stages"]["platform_setup"]
    assert platform_stage["status"] == "blocked"
    assert platform_stage.get("blocked_by") == ["service_registration"]
    update_stage = status["stages"]["update_listener"]
    assert update_stage["status"] == "blocked"
    assert update_stage.get("blocked_by") == ["platform_setup"]
    assert {
        "profile_registry",
        "service_registration",
        "platform_setup",
        "cloud_sync",
        "calibration_services",
        "entity_validation",
        "update_listener",
    }.issubset(set(status["blocked"]))
    metrics = status["metrics"]
    assert metrics["required_total"] >= 1
    assert "profile_store" in metrics["pending_required"]
    assert metrics["next_required_stage"] in metrics["pending_required"]
    assert stored["onboarding_ready"] is False

    issue_id, issue_payload = created[-1]
    assert "profile_store" in issue_id
    assert issue_payload["translation_placeholders"]["stage"]

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)
    assert diagnostics["schema_version"] == 10
    assert "profile_store" in diagnostics["onboarding_errors"]
    assert diagnostics["onboarding_status"]["stages"]["profile_store"]["status"] == "failed"
    assert diagnostics["onboarding_status"]["metrics"]["next_required_stage"]
    assert diagnostics["onboarding_status"]["blocked"]
    assert diagnostics["onboarding_status"]["warnings"] == []
    assert diagnostics["onboarding_ready"] is False
    assert diagnostics["onboarding_metrics"]["next_required_stage"]
    stage_state = diagnostics["onboarding_stage_state"]["profile_store"]
    assert stage_state["attempts"] == 1
    assert "last_failure" in stage_state
    history = diagnostics.get("onboarding_history")
    assert isinstance(history, list) and history
    diag_timeline = diagnostics.get("onboarding_timeline")
    assert isinstance(diag_timeline, list) and diag_timeline
    assert diag_timeline[-1]["stage"] in {
        "profile_registry",
        "service_registration",
        "platform_setup",
        "update_listener",
    }

    created.clear()
    monkeypatch.setattr(
        "custom_components.horticulture_assistant.__init__.ProfileStore.async_init",
        AsyncMock(return_value=None),
    )

    assert await async_setup_entry(hass, entry)

    assert dataset_health_mock.await_count == 2
    assert coordinator_refresh_mock.await_count == 1
    assert profile_registry_init.await_count == 1
    assert cloud_start_mock.await_count == 1
    assert register_all_mock.await_count == 1
    assert setup_services_mock.await_count == 1
    assert http_register_mock.await_count == 2

    stored = hass.data[DOMAIN][entry.entry_id]
    assert not stored.get("onboarding_errors")
    assert stored["onboarding_status"]["stages"]["profile_store"]["status"] == "success"
    assert stored["onboarding_status"]["metrics"]["pending_required"] == []
    assert stored["onboarding_status"]["metrics"]["next_required_stage"] is None
    assert stored["onboarding_status"]["blocked"] == []
    assert stored["onboarding_metrics"]["progress"] == 1.0
    assert stored["onboarding_status"]["stages"]["cloud_sync"]["status"] == "warning"
    assert "cloud_sync" in stored["onboarding_status"]["warnings"]
    assert stored["onboarding_metrics"]["warnings_total"] >= 1
    assert "cloud_sync" in stored["onboarding_metrics"]["warnings"]
    warnings_map = stored.get("onboarding_warnings")
    assert warnings_map and warnings_map["cloud_sync"]
    assert stored["onboarding_ready"] is True
    assert any("profile_store" in issue for issue in deleted)
    assert stored["onboarding_stage_state"]["profile_store"]["attempts"] == 2
    assert "last_success" in stored["onboarding_stage_state"]["profile_store"]
    assert len(stored["onboarding_history"]) >= 2
    timeline = stored["onboarding_timeline"]
    profile_events = [event for event in timeline if event["stage"] == "profile_store"]
    assert profile_events[-1]["status"] == "success"
    assert profile_events[-1]["attempt"] == 2
    cloud_events = [event for event in timeline if event["stage"] == "cloud_sync"]
    assert cloud_events[-1]["status"] == "warning"
    assert cloud_events[-1].get("warnings")
