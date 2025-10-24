import pytest

from custom_components.horticulture_assistant.const import (
    DOMAIN,
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

    monkeypatch.setattr(
        "custom_components.horticulture_assistant.health_monitor.load_dataset",
        lambda _filename: {},
    )

    check = hass.data[DOMAIN]["dataset_monitor_check"]
    await check(None)

    assert any(item["notification_id"] == NOTIFICATION_DATASET_HEALTH for item in dismissals)

    await async_release_dataset_health(hass)
