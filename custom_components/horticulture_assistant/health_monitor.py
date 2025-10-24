"""Background monitors for dataset health and persistent notifications."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import timedelta
from typing import Any

from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers.event import async_track_time_interval

from .const import DOMAIN, NOTIFICATION_DATASET_HEALTH
from .engine.plant_engine.utils import load_dataset

DATASET_CHECK_INTERVAL = timedelta(hours=6)

# Representative datasets that confirm the bundled catalogues were loaded.
CRITICAL_DATASETS: tuple[tuple[str, str], ...] = (
    ("Fertilizer catalogue", "fertilizers/fertilizer_products.json"),
    ("Crop targets", "crops/targets.json"),
    ("Irrigation schedules", "irrigation/intervals.json"),
    ("Deficiency symptoms", "diagnostics/deficiency_symptoms.json"),
)


async def async_setup_dataset_health(hass: HomeAssistant) -> CALLBACK_TYPE | None:
    """Start a periodic dataset integrity check if not already running."""

    domain_data = hass.data.setdefault(DOMAIN, {})
    if monitor := domain_data.get("dataset_monitor_unsub"):
        domain_data["dataset_monitor_refs"] = domain_data.get("dataset_monitor_refs", 0) + 1
        return monitor

    async def _async_check(_now: Any | None = None) -> None:
        failures = await hass.async_add_executor_job(_collect_dataset_failures)
        await _async_publish_dataset_state(hass, failures)

    def _handle_start(_: Any) -> None:
        hass.async_create_task(_async_check(None))

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, _handle_start)
    unsub = async_track_time_interval(hass, _async_check, DATASET_CHECK_INTERVAL)
    domain_data["dataset_monitor_unsub"] = unsub
    domain_data["dataset_monitor_refs"] = 1
    domain_data["dataset_monitor_check"] = _async_check
    await _async_check(None)
    return unsub


def _collect_dataset_failures() -> list[tuple[str, str, str]]:
    failures: list[tuple[str, str, str]] = []
    for label, filename in CRITICAL_DATASETS:
        try:
            load_dataset(filename)
        except Exception as err:  # pragma: no cover - logged via notification
            failures.append((label, filename, str(err)))
    return failures


async def _async_publish_dataset_state(hass: HomeAssistant, failures: Iterable[tuple[str, str, str]]) -> None:
    issues = list(failures)
    if not issues:
        await _async_dismiss_notification(hass, NOTIFICATION_DATASET_HEALTH)
        hass.data.setdefault(DOMAIN, {})["dataset_monitor_digest"] = None
        return

    digest = tuple(sorted(issues))
    domain_data = hass.data.setdefault(DOMAIN, {})
    if domain_data.get("dataset_monitor_digest") == digest:
        return

    domain_data["dataset_monitor_digest"] = digest
    lines = [
        "The integration could not load the following reference datasets:",
        "",
    ]
    for label, filename, err in issues:
        lines.append(f"- {label} ({filename}): {err}")
    lines.append("")
    lines.append("Fix the dataset, remove any broken overrides, then reload the integration.")
    message = "\n".join(lines)
    await _async_create_notification(
        hass,
        title="Horticulture Assistant data error",
        message=message,
        notification_id=NOTIFICATION_DATASET_HEALTH,
    )


async def _async_create_notification(
    hass: HomeAssistant,
    *,
    title: str,
    message: str,
    notification_id: str,
) -> None:
    try:
        await hass.services.async_call(
            "persistent_notification",
            "create",
            {
                "title": title,
                "message": message,
                "notification_id": notification_id,
            },
            blocking=True,
        )
    except KeyError:  # pragma: no cover - service missing in unit tests
        return


async def async_release_dataset_health(hass: HomeAssistant) -> None:
    """Decrease the dataset monitor reference count and cancel when unused."""

    domain_data = hass.data.get(DOMAIN, {})
    refs = domain_data.get("dataset_monitor_refs", 0)
    if refs <= 1:
        domain_data["dataset_monitor_refs"] = 0
        unsub = domain_data.pop("dataset_monitor_unsub", None)
        domain_data.pop("dataset_monitor_check", None)
        domain_data.pop("dataset_monitor_digest", None)
        if unsub:
            try:
                unsub()
            except Exception:  # pragma: no cover - defensive cleanup
                return
    else:
        domain_data["dataset_monitor_refs"] = refs - 1


async def _async_dismiss_notification(hass: HomeAssistant, notification_id: str) -> None:
    try:
        await hass.services.async_call(
            "persistent_notification",
            "dismiss",
            {"notification_id": notification_id},
            blocking=True,
        )
    except KeyError:  # pragma: no cover - service missing in unit tests
        return
