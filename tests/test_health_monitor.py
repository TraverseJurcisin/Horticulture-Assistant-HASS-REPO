import pytest

from custom_components.horticulture_assistant.const import (
    DOMAIN,
    ISSUE_DATASET_HEALTH_PREFIX,
    NOTIFICATION_DATASET_HEALTH,
)
from custom_components.horticulture_assistant.health_monitor import (
    async_release_dataset_health,
    async_setup_dataset_health,
)


@pytest.mark.asyncio
async def test_dataset_monitor_reports_and_clears_notifications(hass, monkeypatch):
    notifications: list[dict] = []
    dismissals: list[dict] = []

    hass.services.async_register(
        "persistent_notification",
        "create",
        lambda call: notifications.append(call.data),
    )
    hass.services.async_register(
        "persistent_notification",
        "dismiss",
        lambda call: dismissals.append(call.data),
    )

    created: list[tuple[str, dict]] = []
    deleted: list[str] = []

    monkeypatch.setattr(
        "custom_components.horticulture_assistant.health_monitor.ir.async_create_issue",
        lambda *args, **kwargs: created.append((args[2], kwargs)),
    )
    monkeypatch.setattr(
        "custom_components.horticulture_assistant.health_monitor.ir.async_delete_issue",
        lambda *args, **_kwargs: deleted.append(args[2]),
    )

    def _raise(_filename: str):
        raise ValueError("bad data")

    monkeypatch.setattr(
        "custom_components.horticulture_assistant.health_monitor.load_dataset",
        _raise,
    )

    await async_setup_dataset_health(hass)

    assert notifications
    note = notifications[-1]
    assert note["notification_id"] == NOTIFICATION_DATASET_HEALTH
    assert "bad data" in note["message"]
    assert created
    issue_id, metadata = created[-1]
    assert issue_id.startswith(ISSUE_DATASET_HEALTH_PREFIX)
    assert metadata["translation_placeholders"]["error"] == "bad data"

    monkeypatch.setattr(
        "custom_components.horticulture_assistant.health_monitor.load_dataset",
        lambda _filename: {},
    )

    check = hass.data[DOMAIN]["dataset_monitor_check"]
    await check(None)

    assert any(item["notification_id"] == NOTIFICATION_DATASET_HEALTH for item in dismissals)
    assert issue_id in deleted

    await async_release_dataset_health(hass)


@pytest.mark.asyncio
async def test_dataset_monitor_release_clears_outstanding_issues(hass, monkeypatch):
    notifications: list[dict] = []
    dismissals: list[dict] = []
    created: list[str] = []
    deleted: list[str] = []

    hass.services.async_register(
        "persistent_notification",
        "create",
        lambda call: notifications.append(call.data),
    )
    hass.services.async_register(
        "persistent_notification",
        "dismiss",
        lambda call: dismissals.append(call.data),
    )

    monkeypatch.setattr(
        "custom_components.horticulture_assistant.health_monitor.ir.async_create_issue",
        lambda *args, **_kwargs: created.append(args[2]),
    )
    monkeypatch.setattr(
        "custom_components.horticulture_assistant.health_monitor.ir.async_delete_issue",
        lambda *args, **_kwargs: deleted.append(args[2]),
    )

    def _raise(_filename: str):
        raise ValueError("boom")

    monkeypatch.setattr(
        "custom_components.horticulture_assistant.health_monitor.load_dataset",
        _raise,
    )

    await async_setup_dataset_health(hass)

    assert created
    outstanding = created[-1]
    assert notifications

    await async_release_dataset_health(hass)

    assert outstanding in deleted
    assert any(item["notification_id"] == NOTIFICATION_DATASET_HEALTH for item in dismissals)
