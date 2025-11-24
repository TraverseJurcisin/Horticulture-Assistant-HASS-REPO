from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .const import CONF_API_KEY, DOMAIN
from .profile_monitor import ProfileMonitor
from .profile_registry import ProfileRegistry
from .utils.entry_helpers import entry_device_identifier, profile_device_identifier, serialise_device_info

TO_REDACT = {CONF_API_KEY}
_ONBOARDING_TIMELINE_LIMIT = 50


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    data = hass.data.get(DOMAIN, {})
    entry_data = data.get(entry.entry_id)
    reg: ProfileRegistry | None = data.get("registry")
    payload: dict[str, Any] = {
        "entry": {
            "title": entry.title,
            "data": dict(entry.data),
            "options": {key: ("***" if key == CONF_API_KEY else value) for key, value in entry.options.items()},
        },
        "profile_count": 0,
        "profiles": [],
        "coordinators": {},
        "schema_version": 10,
    }
    if reg:
        if hasattr(reg, "diagnostics_snapshot"):
            profiles = reg.diagnostics_snapshot()
            payload["profiles"] = profiles
            payload["profile_count"] = len(profiles)
            totals = {
                "run_events": sum(len(item.get("run_history", ())) for item in profiles),
                "harvest_events": sum(len(item.get("harvest_history", ())) for item in profiles),
                "statistics": sum(len(item.get("statistics", ())) for item in profiles),
            }
            payload["profile_totals"] = totals
        else:
            profiles = reg.summaries()
            payload["profiles"] = profiles
            payload["profile_count"] = len(profiles)
        history_index = await reg.async_history_index()
        if history_index:
            payload["history_exports"] = {
                "enabled": True,
                "profiles": history_index,
            }

    for key, coord in data.items():
        if not key.startswith("coordinator"):
            continue
        payload["coordinators"][key] = {
            "last_update_success": getattr(coord, "last_update_success", False),
            "last_update": getattr(coord, "last_update", None),
            "last_exception": getattr(coord, "last_exception", None),
        }

    if isinstance(entry_data, dict):
        manager = entry_data.get("cloud_sync_manager")
        if manager:
            payload["cloud_sync_status"] = manager.status()

        onboarding_errors = entry_data.get("onboarding_errors")
        if isinstance(onboarding_errors, Mapping) and onboarding_errors:
            payload["onboarding_errors"] = {
                stage: dict(info) if isinstance(info, Mapping) else {"error": info}
                for stage, info in onboarding_errors.items()
            }

        onboarding_status = entry_data.get("onboarding_status")
        if isinstance(onboarding_status, Mapping) and onboarding_status:
            stages = onboarding_status.get("stages")
            if isinstance(stages, Mapping):
                timeline = onboarding_status.get("timeline")
                payload["onboarding_status"] = {
                    "order": list(onboarding_status.get("order", [])),
                    "failures": list(onboarding_status.get("failures", [])),
                    "skipped": list(onboarding_status.get("skipped", [])),
                    "blocked": list(onboarding_status.get("blocked", [])),
                    "warnings": list(onboarding_status.get("warnings", [])),
                    "ready": bool(onboarding_status.get("ready")),
                    "metrics": (
                        dict(onboarding_status.get("metrics", {}))
                        if isinstance(onboarding_status.get("metrics"), Mapping)
                        else onboarding_status.get("metrics", {})
                    ),
                    "stages": {
                        stage: dict(info) if isinstance(info, Mapping) else {"status": info}
                        for stage, info in stages.items()
                    },
                    "timeline": list(timeline) if isinstance(timeline, list) else [],
                }
                warning_details = onboarding_status.get("warning_details")
                if isinstance(warning_details, Mapping):
                    payload["onboarding_status"]["warning_details"] = {
                        stage: list(messages) if isinstance(messages, list | tuple | set) else [messages]
                        for stage, messages in warning_details.items()
                    }

        if "onboarding_ready" in entry_data:
            payload["onboarding_ready"] = bool(entry_data.get("onboarding_ready"))

        metrics = entry_data.get("onboarding_metrics")
        if isinstance(metrics, Mapping) and metrics:
            payload["onboarding_metrics"] = dict(metrics)

        warnings_map = entry_data.get("onboarding_warnings")
        if isinstance(warnings_map, Mapping) and warnings_map:
            payload["onboarding_warnings"] = {
                stage: list(messages) if isinstance(messages, list | tuple | set) else [messages]
                for stage, messages in warnings_map.items()
            }

        registry_warnings = entry_data.get("profile_registry_warnings")
        if isinstance(registry_warnings, list) and registry_warnings:
            payload["profile_registry_warnings"] = list(registry_warnings)

        timeline = entry_data.get("onboarding_timeline")
        if isinstance(timeline, list) and timeline:
            payload["onboarding_timeline"] = list(timeline[-_ONBOARDING_TIMELINE_LIMIT:])

        stage_state = entry_data.get("onboarding_stage_state")
        if isinstance(stage_state, Mapping) and stage_state:
            payload["onboarding_stage_state"] = {
                stage: dict(info) if isinstance(info, Mapping) else {"value": info}
                for stage, info in stage_state.items()
            }

        history = entry_data.get("onboarding_history")
        if isinstance(history, list) and history:
            payload["onboarding_history"] = list(history[-5:])

        last_completed = entry_data.get("onboarding_last_completed")
        if isinstance(last_completed, str) and last_completed:
            payload["onboarding_last_completed"] = last_completed

        devices: dict[str, Any] = {}
        entry_device = entry_data.get("entry_device_info")
        stored_entry = entry_data.get("config_entry")
        entry_id_value = getattr(stored_entry, "entry_id", entry.entry_id)
        entry_identifier = entry_data.get("entry_device_identifier")
        if entry_identifier is None and entry_id_value:
            entry_identifier = entry_device_identifier(entry_id_value)

        if entry_device:
            devices["entry"] = serialise_device_info(
                entry_device,
                fallback_identifier=entry_identifier,
            )

        profile_devices = entry_data.get("profile_devices")
        if isinstance(profile_devices, dict):
            devices["profiles"] = {}
            for profile_id, info in profile_devices.items():
                canonical_profile_id = str(profile_id).strip()
                fallback_identifier = profile_device_identifier(
                    entry_id_value,
                    canonical_profile_id or None,
                )
                devices["profiles"][profile_id] = serialise_device_info(
                    info,
                    fallback_identifier=fallback_identifier,
                    fallback_via_device=entry_identifier,
                )
        if devices:
            payload["devices"] = devices

        profile_contexts = entry_data.get("profile_contexts")
        if isinstance(profile_contexts, Mapping):
            monitors: dict[str, Any] = {}
            for profile_id, context in profile_contexts.items():
                try:
                    monitors[profile_id] = ProfileMonitor(hass, context).evaluate().as_diagnostics()
                except Exception:  # pragma: no cover - diagnostics should not fail
                    continue
            if monitors:
                payload["profile_monitors"] = monitors

    payload["log_tail"] = await hass.async_add_executor_job(_read_log_tail, hass, entry)
    return async_redact_data(payload, TO_REDACT)


def _read_log_tail(hass: HomeAssistant, entry) -> list[str]:
    """Return a masked tail of the core log file for quick troubleshooting."""

    log_path = Path(hass.config.path("home-assistant.log"))
    if not log_path.exists():
        return []

    try:
        lines = log_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except Exception:
        return []

    tail = lines[-200:]
    api_key = entry.data.get(CONF_API_KEY) or entry.options.get(CONF_API_KEY)
    if not api_key:
        return tail

    secret = str(api_key)
    return [line.replace(secret, "***") for line in tail]
