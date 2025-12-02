from __future__ import annotations

import asyncio
import contextlib
import importlib
import importlib.util
import inspect
import logging
import sys
import time
from collections.abc import Mapping
from copy import deepcopy
from datetime import UTC, datetime
from enum import StrEnum
from types import SimpleNamespace
from typing import Any

import homeassistant.helpers.config_validation as cv
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

try:
    from homeassistant.helpers import issue_registry as ir
except (ImportError, ModuleNotFoundError):  # pragma: no cover - executed in tests

    class IssueSeverity(StrEnum):
        ERROR = "error"
        WARNING = "warning"

    ir = SimpleNamespace(  # type: ignore[assignment]
        IssueSeverity=IssueSeverity,
        async_create_issue=lambda *_args, **_kwargs: None,
        async_delete_issue=lambda *_args, **_kwargs: None,
    )

try:  # pragma: no cover - allow running tests without Home Assistant dispatcher
    from homeassistant.helpers.dispatcher import async_dispatcher_send
except (ImportError, ModuleNotFoundError):  # pragma: no cover - executed in stubbed env

    def async_dispatcher_send(*_args, **_kwargs):
        return None


from . import services as ha_services
from .api import ChatApi
from .cloudsync import CloudSyncManager, CloudSyncPublisher
from .const import (
    CONF_API_KEY,
    CONF_BASE_URL,
    CONF_KEEP_STALE,
    CONF_MODEL,
    CONF_PLANT_ID,
    CONF_PLANT_NAME,
    CONF_PLANT_TYPE,
    CONF_PROFILE_SCOPE,
    CONF_PROFILES,
    CONF_UPDATE_INTERVAL,
    DEFAULT_BASE_URL,
    DEFAULT_KEEP_STALE,
    DEFAULT_MODEL,
    DEFAULT_UPDATE_MINUTES,
    DOMAIN,
    PLATFORMS,
    PROFILE_SCOPE_DEFAULT,
    signal_profile_contexts_updated,
)
from .coordinator import HorticultureCoordinator
from .coordinator_ai import HortiAICoordinator
from .coordinator_local import HortiLocalCoordinator
from .entity_utils import ensure_entities_exist
from .health_monitor import async_release_dataset_health, async_setup_dataset_health
from .http import async_register_http_views
from .profile.compat import sync_thresholds
from .profile.utils import ensure_sections
from .profile_registry import ProfileRegistry
from .profile_store import ProfileStore

try:
    from .storage import DEFAULT_DATA, LocalStore
except ImportError:  # pragma: no cover - fallback for stubbed tests
    from .storage import LocalStore  # type: ignore[misc]

    DEFAULT_DATA: dict[str, Any] = {}
from .utils.entry_helpers import (
    backfill_profile_devices_from_options,
    ensure_all_profile_devices_registered,
    get_entry_data,
    get_entry_plant_info,
    get_primary_profile_id,
    get_primary_profile_sensors,
    remove_entry_data,
    store_entry_data,
    update_entry_data,
)
from .utils.intervals import _normalise_update_minutes
from .utils.paths import ensure_local_data_paths

_CALIBRATION_SPEC = importlib.util.find_spec("custom_components.horticulture_assistant.calibration.services")
calibration_services = None
if _CALIBRATION_SPEC is not None:
    calibration_services = importlib.import_module("custom_components.horticulture_assistant.calibration.services")

__all__ = [
    "async_setup",
    "async_setup_entry",
    "async_migrate_entry",
    "async_unload_entry",
]

_LOGGER = logging.getLogger(__name__)
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


def _utcnow() -> str:
    """Return an ISO-8601 timestamp in UTC."""

    return datetime.now(tz=UTC).isoformat()


_ONBOARDING_ISSUE_PREFIX = "onboarding_stage"
_ONBOARDING_STAGE_LABELS: dict[str, str] = {
    "local_paths": "initial data directories",
    "dataset_health": "dataset health checks",
    "local_store": "local data store",
    "profile_store": "profile library",
    "profile_registry": "profile registry",
    "coordinator_refresh": "initial data refresh",
    "coordinator_ai_refresh": "initial AI refresh",
    "coordinator_local_refresh": "initial local refresh",
    "cloud_sync": "cloud sync startup",
    "service_registration": "service registration",
    "service_setup": "service setup",
    "calibration_services": "calibration services",
    "platform_setup": "platform setup",
    "http_views": "HTTP API registration",
    "entity_validation": "entity validation",
    "update_listener": "options update listener",
}
_ONBOARDING_STAGE_META: dict[str, dict[str, Any]] = {
    "local_paths": {"required": True},
    "dataset_health": {"required": False, "depends_on": ("local_paths",)},
    "local_store": {"required": True, "depends_on": ("local_paths",)},
    "profile_store": {"required": True, "depends_on": ("local_store",)},
    "profile_registry": {"required": True, "depends_on": ("profile_store",)},
    "coordinator_refresh": {"required": True, "depends_on": ("local_store",)},
    "coordinator_ai_refresh": {"required": False, "depends_on": ("local_store",)},
    "coordinator_local_refresh": {"required": False, "depends_on": ("local_store",)},
    "cloud_sync": {"required": False, "depends_on": ("profile_registry",)},
    "service_registration": {
        "required": True,
        "depends_on": (
            "profile_registry",
            "coordinator_refresh",
        ),
    },
    "service_setup": {"required": False, "depends_on": ("service_registration",)},
    "calibration_services": {"required": False, "depends_on": ("service_registration",)},
    "platform_setup": {"required": True, "depends_on": ("service_registration",)},
    "http_views": {"required": False},
    "entity_validation": {
        "required": False,
        "depends_on": (
            "profile_registry",
            "coordinator_refresh",
        ),
    },
    "update_listener": {"required": False, "depends_on": ("platform_setup",)},
}
_STAGE_READY_STATUSES = {"success", "warning"}
_STAGE_SATISFIED_STATUSES = {"success", "skipped", "warning"}


async def _async_forward_entry_platforms(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Forward a config entry to all platforms with legacy fallbacks."""

    forward_setups = getattr(hass.config_entries, "async_forward_entry_setups", None)
    legacy_forward = getattr(hass.config_entries, "async_forward_entry_setup", None)

    if callable(forward_setups):
        return bool(await forward_setups(entry, PLATFORMS))

    if not callable(legacy_forward):
        return False

    async def _forward(platform: str) -> Any:
        result = legacy_forward(entry, platform)
        if inspect.isawaitable(result):
            return await result
        return result

    results = await asyncio.gather(
        *(_forward(platform) for platform in PLATFORMS),
        return_exceptions=True,
    )
    for result in results:
        if isinstance(result, Exception):
            raise result
    return all(bool(result) for result in results)


def _stage_ready(status: str | None) -> bool:
    return status in _STAGE_READY_STATUSES


def _stage_satisfied(status: str | None) -> bool:
    return status in _STAGE_SATISFIED_STATUSES


_ONBOARDING_STAGE_ORDER: tuple[str, ...] = tuple(_ONBOARDING_STAGE_LABELS)
_ONBOARDING_TIMELINE_LIMIT = 50


def __getattr__(name: str) -> Any:
    """Dynamically expose child modules as package attributes.

    Tests patch paths like ``custom_components.horticulture_assistant.profile.store``
    before explicitly importing those submodules. Python only populates attributes
    for child modules on a package once they have been imported, so lookups would
    fail with ``AttributeError``. Expose a lazy importer that resolves the module
    when an attribute is first accessed, mirroring Home Assistant's packaging.
    """

    try:
        module = importlib.import_module(f".{name}", __name__)
    except ModuleNotFoundError as exc:  # pragma: no cover - passthrough to default error
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc
    else:
        setattr(sys.modules[__name__], name, module)
        return module


def _stage_issue_id(entry_id: str | None, stage: str) -> str:
    identifier = entry_id or "unknown"
    safe_stage = stage.replace(" ", "_")
    return f"{_ONBOARDING_ISSUE_PREFIX}_{identifier}_{safe_stage}"


def _stage_label(stage: str) -> str:
    return _ONBOARDING_STAGE_LABELS.get(stage, stage.replace("_", " "))


class _OnboardingManager:
    """Utility managing onboarding stage outcomes and diagnostics."""

    __slots__ = (
        "hass",
        "entry",
        "entry_data",
        "status",
        "_state",
        "_history",
        "_timeline",
        "_warnings",
    )

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, entry_data: dict[str, Any]):
        self.hass = hass
        self.entry = entry
        self.entry_data = entry_data
        self.status: dict[str, dict[str, Any]] = {}
        self._state: dict[str, dict[str, Any]] = {}
        self._history: list[dict[str, Any]] = []
        self._warnings: dict[str, list[str]] = {}
        self._ensure_state_containers()

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def _ensure_state_containers(self) -> None:
        """Ensure state containers exist on the entry data."""

        state = self.entry_data.get("onboarding_stage_state")
        if isinstance(state, dict):
            self._state = state
        else:
            self._state = {}
            self.entry_data["onboarding_stage_state"] = self._state

        history = self.entry_data.get("onboarding_history")
        if isinstance(history, list):
            self._history = history
        else:
            self._history = []
            self.entry_data["onboarding_history"] = self._history

        timeline = self.entry_data.get("onboarding_timeline")
        if isinstance(timeline, list):
            self._timeline = timeline
        else:
            self._timeline = []
            self.entry_data["onboarding_timeline"] = self._timeline

        warnings = self.entry_data.get("onboarding_warnings")
        if isinstance(warnings, dict):
            cleaned: dict[str, list[str]] = {}
            for stage, messages in warnings.items():
                if not isinstance(stage, str):
                    continue
                if isinstance(messages, list | tuple | set):
                    cleaned[stage] = [str(msg) for msg in messages if str(msg)]
            self._warnings = cleaned
        else:
            self._warnings = {}
        self.entry_data["onboarding_warnings"] = self._warnings

    def _sync_entry_warnings(self) -> None:
        if not self._warnings:
            self._warnings = {}
            self.entry_data.pop("onboarding_warnings", None)
            return
        cleaned = {
            stage: [str(msg) for msg in messages if str(msg)] for stage, messages in self._warnings.items() if messages
        }
        if cleaned:
            self._warnings = cleaned
            self.entry_data["onboarding_warnings"] = self._warnings
        else:
            self._warnings = {}
            self.entry_data.pop("onboarding_warnings", None)

    def _meta(self, stage: str) -> dict[str, Any]:
        return _ONBOARDING_STAGE_META.get(stage, {})

    def _stage_state(self, stage: str) -> dict[str, Any]:
        """Return the mutable state dictionary for ``stage``."""

        state = self._state.get(stage)
        if not isinstance(state, dict):
            state = {"attempts": 0}
            self._state[stage] = state
        state.setdefault("attempts", int(state.get("attempts", 0)))
        return state

    def _stage_status(self, stage: str) -> str | None:
        """Return the last known status for ``stage``."""

        info = self.status.get(stage)
        if isinstance(info, dict):
            status = info.get("status")
            if isinstance(status, str):
                return status
        state = self._state.get(stage)
        if isinstance(state, dict):
            last_status = state.get("last_status")
            if isinstance(last_status, str):
                return last_status
        return None

    def _dependencies_ready(self, stage: str) -> tuple[bool, list[str]]:
        """Return whether dependencies for ``stage`` are satisfied."""

        meta = self._meta(stage)
        depends_on = meta.get("depends_on") or ()
        if not depends_on:
            return True, []
        blocked: list[str] = []
        for dependency in depends_on:
            status = self._stage_status(dependency)
            if _stage_satisfied(status):
                continue
            blocked.append(dependency)
        return not blocked, blocked

    def ensure_dependencies(
        self,
        stage: str,
        *,
        reason: str | None = None,
        dependencies: tuple[str, ...] | list[str] | None = None,
    ) -> bool:
        """Ensure dependencies for ``stage`` are satisfied, blocking if not."""

        ready, blocked = self._dependencies_ready(stage)
        if ready:
            return True
        deps: tuple[str, ...]
        if dependencies is not None:
            deps = tuple(dependencies)
        elif blocked:
            deps = tuple(blocked)
        else:
            meta = self._meta(stage)
            depends_on = meta.get("depends_on") or ()
            deps = tuple(depends_on)
        if not reason:
            if deps:
                labels = ", ".join(_stage_label(dep) for dep in deps)
                reason = f"dependencies incomplete: {labels}"
            else:
                reason = "dependencies incomplete"
        self.block(stage, reason, dependencies=deps)
        return False

    def _begin_stage(self, stage: str) -> dict[str, Any]:
        """Record the start of ``stage`` and increment attempts."""

        state = self._stage_state(stage)
        attempts = int(state.get("attempts", 0)) + 1
        state["attempts"] = attempts
        timestamp = _utcnow()
        state["last_attempt"] = timestamp
        state["_last_started"] = timestamp
        return state

    def _complete_stage(
        self,
        stage: str,
        status: str,
        *,
        state: dict[str, Any] | None = None,
        reason: str | None = None,
        error: str | None = None,
        exception: str | None = None,
        duration: float | None = None,
    ) -> dict[str, Any]:
        """Store the result of ``stage`` and return the status payload."""

        state = state or self._stage_state(stage)
        timestamp = _utcnow()
        state["last_status"] = status
        state["updated"] = timestamp
        rounded: float | None = None
        if duration is not None:
            rounded = round(duration, 4)
            state["last_duration"] = rounded

        if status != "warning":
            self._warnings.pop(stage, None)
        if status == "success":
            state["last_success"] = timestamp
            state.pop("last_error", None)
            state.pop("last_failure", None)
            state.pop("blocked_by", None)
            state.pop("warnings", None)
            state.pop("last_warning", None)
        elif status == "failed":
            state["last_failure"] = timestamp
            if error:
                state["last_error"] = error
            state.pop("warnings", None)
            state.pop("last_warning", None)
        elif status == "skipped":
            state["last_skipped"] = timestamp
            state.pop("blocked_by", None)
            state.pop("warnings", None)
            state.pop("last_warning", None)
        elif status == "blocked":
            blocked_by = state.get("blocked_by")
            if blocked_by:
                payload_blocked = [str(dep) for dep in blocked_by if dep]
                if payload_blocked:
                    state["blocked_by"] = payload_blocked
            state.pop("warnings", None)
            state.pop("last_warning", None)
        elif status == "warning":
            warnings = state.setdefault("warnings", [])
            if reason and reason not in warnings:
                warnings.append(reason)
            state["last_warning"] = timestamp
            state.pop("blocked_by", None)
            self._warnings[stage] = list(warnings)

        blocked_by = state.get("blocked_by")

        payload: dict[str, Any] = {
            "stage": stage,
            "label": _stage_label(stage),
            "status": status,
            "required": bool(self._meta(stage).get("required", False)),
            "attempts": int(state.get("attempts", 0)),
        }
        if reason:
            payload["reason"] = reason
        if error:
            payload["error"] = error
        if exception:
            payload["exception"] = exception
        if rounded is not None:
            payload["duration"] = rounded
        last_attempt = state.get("last_attempt")
        if last_attempt:
            payload["last_attempt"] = last_attempt
        last_success = state.get("last_success")
        if last_success:
            payload["last_success"] = last_success
        last_failure = state.get("last_failure")
        if last_failure:
            payload["last_failure"] = last_failure
        last_skipped = state.get("last_skipped")
        if last_skipped:
            payload["last_skipped"] = last_skipped
        if blocked_by and status == "blocked":
            payload["blocked_by"] = list(blocked_by)
        if status == "warning":
            warnings = state.get("warnings")
            if warnings:
                payload["warnings"] = list(warnings)
        self.status[stage] = payload
        self._record_timeline_event(
            stage,
            payload,
            state=state,
            reason=reason,
            error=error,
            exception=exception,
            duration=rounded,
        )
        self._sync_entry_warnings()
        return payload

    def _record_timeline_event(
        self,
        stage: str,
        payload: Mapping[str, Any],
        *,
        state: Mapping[str, Any],
        reason: str | None,
        error: str | None,
        exception: str | None,
        duration: float | None,
    ) -> None:
        """Append a serialisable timeline event for ``stage``."""

        event: dict[str, Any] = {
            "stage": stage,
            "label": payload.get("label", _stage_label(stage)),
            "status": payload.get("status", "unknown"),
            "attempt": int(state.get("attempts", 0)),
        }

        started = state.get("_last_started") or state.get("last_attempt")
        if started:
            event["started_at"] = str(started)
        completed = state.get("updated")
        event["completed_at"] = str(completed) if completed else _utcnow()
        if duration is not None:
            event["duration"] = duration
        if reason:
            event["reason"] = reason
        if error:
            event["error"] = error
        if exception:
            event["exception"] = exception

        blocked = state.get("blocked_by")
        if blocked and payload.get("status") == "blocked":
            event["blocked_by"] = [str(dep) for dep in blocked if dep]
        warnings = payload.get("warnings")
        if warnings:
            event["warnings"] = list(warnings)

        self._timeline.append(event)
        if len(self._timeline) > _ONBOARDING_TIMELINE_LIMIT:
            del self._timeline[:-_ONBOARDING_TIMELINE_LIMIT]
        # ensure the list stored on the entry data stays in sync
        self.entry_data["onboarding_timeline"] = self._timeline
        # cleanup internal marker so stage_state remains user-friendly
        if isinstance(state, dict) and "_last_started" in state:
            state.pop("_last_started", None)

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------
    def rebind(self, entry_data: dict[str, Any]) -> None:
        """Update the entry data reference used for recording errors."""

        self.entry_data = entry_data
        self._ensure_state_containers()

    def skip(self, stage: str, reason: str) -> tuple[bool, None]:
        """Skip ``stage`` while recording the reason for diagnostics."""

        _clear_onboarding_error(self.hass, self.entry, self.entry_data, stage)
        state = self._stage_state(stage)
        state["last_attempt"] = _utcnow()
        state.pop("blocked_by", None)
        self._complete_stage(stage, "skipped", state=state, reason=reason)
        return False, None

    def block(
        self,
        stage: str,
        reason: str,
        *,
        dependencies: tuple[str, ...] | list[str] | None = None,
    ) -> tuple[bool, None]:
        """Mark ``stage`` as blocked by an unmet dependency."""

        _clear_onboarding_error(self.hass, self.entry, self.entry_data, stage)
        state = self._begin_stage(stage)
        if dependencies:
            state["blocked_by"] = [str(dep) for dep in dependencies if dep]
        else:
            state.pop("blocked_by", None)
        self._complete_stage(stage, "blocked", state=state, reason=reason)
        return False, None

    def record_failure(
        self,
        stage: str,
        err: Exception,
        *,
        state: dict[str, Any] | None = None,
        duration: float | None = None,
    ) -> None:
        """Persist an onboarding failure for diagnostics and repairs."""

        _record_onboarding_error(self.hass, self.entry, self.entry_data, stage, err)
        message = str(err) or err.__class__.__name__
        self._complete_stage(
            stage,
            "failed",
            state=state,
            error=message,
            exception=repr(err),
            duration=duration,
        )

    def record_success(
        self,
        stage: str,
        *,
        state: dict[str, Any] | None = None,
        duration: float | None = None,
    ) -> None:
        """Mark ``stage`` as successful and clear outstanding issues."""

        _clear_onboarding_error(self.hass, self.entry, self.entry_data, stage)
        self._complete_stage(stage, "success", state=state, duration=duration)

    def record_warning(
        self,
        stage: str,
        reason: str,
        *,
        state: dict[str, Any] | None = None,
        duration: float | None = None,
    ) -> None:
        """Record a non-fatal warning for ``stage`` while keeping readiness."""

        _clear_onboarding_error(self.hass, self.entry, self.entry_data, stage)
        self._complete_stage(
            stage,
            "warning",
            state=state,
            reason=reason,
            duration=duration,
        )

    async def guard_async(self, stage: str, awaitable) -> tuple[bool, Any]:
        """Await ``awaitable`` while capturing onboarding failures."""

        state = self._begin_stage(stage)
        start = time.perf_counter()
        try:
            result = await awaitable
        except Exception as err:  # pragma: no cover - defensive guard
            _LOGGER.exception(
                "Setup stage %s failed for entry %s: %s",
                stage,
                self.entry.entry_id,
                err,
            )
            duration = time.perf_counter() - start
            self.record_failure(stage, err, state=state, duration=duration)
            return False, None
        duration = time.perf_counter() - start
        self.record_success(stage, state=state, duration=duration)
        return True, result

    async def guard_call(self, stage: str, func, *args, **kwargs) -> tuple[bool, Any]:
        """Invoke ``func`` guarding both sync and async exceptions."""

        state = self._begin_stage(stage)
        start = time.perf_counter()
        try:
            result = func(*args, **kwargs)
        except Exception as err:  # pragma: no cover - defensive guard
            _LOGGER.exception(
                "Setup stage %s failed for entry %s: %s",
                stage,
                self.entry.entry_id,
                err,
            )
            duration = time.perf_counter() - start
            self.record_failure(stage, err, state=state, duration=duration)
            return False, None
        if asyncio.iscoroutine(result):
            try:
                awaited = await result
            except Exception as err:  # pragma: no cover - defensive guard
                _LOGGER.exception(
                    "Setup stage %s failed for entry %s: %s",
                    stage,
                    self.entry.entry_id,
                    err,
                )
                duration = time.perf_counter() - start
                self.record_failure(stage, err, state=state, duration=duration)
                return False, None
            duration = time.perf_counter() - start
            self.record_success(stage, state=state, duration=duration)
            return True, awaited
        duration = time.perf_counter() - start
        self.record_success(stage, state=state, duration=duration)
        return True, result

    def finalise(self) -> dict[str, Any]:
        """Return a serialisable onboarding status summary."""

        summary: dict[str, dict[str, Any]] = {}
        failures: list[str] = []
        skipped: list[str] = []
        blocked: list[str] = []
        warnings: list[str] = []

        for stage in _ONBOARDING_STAGE_ORDER:
            info = self.status.get(stage)
            state = self._state.get(stage, {})
            if info is None:
                info = {
                    "stage": stage,
                    "label": _stage_label(stage),
                    "status": "pending",
                    "required": bool(self._meta(stage).get("required", False)),
                    "attempts": int(state.get("attempts", 0)),
                }
            else:
                info = dict(info)
                info.setdefault("attempts", int(state.get("attempts", 0)))
            if "last_attempt" not in info and state.get("last_attempt"):
                info["last_attempt"] = state["last_attempt"]
            if "last_success" not in info and state.get("last_success"):
                info["last_success"] = state["last_success"]
            if "last_failure" not in info and state.get("last_failure"):
                info["last_failure"] = state["last_failure"]
            if "warnings" not in info and state.get("warnings"):
                info["warnings"] = list(state.get("warnings", ()))
            if "last_warning" not in info and state.get("last_warning"):
                info["last_warning"] = state["last_warning"]

            status = info.get("status")
            if status == "failed":
                failures.append(stage)
            elif status == "blocked":
                blocked.append(stage)
            elif status == "skipped":
                skipped.append(stage)
            elif status == "warning":
                warnings.append(stage)
            summary[stage] = info

        ready = True
        for stage, meta in _ONBOARDING_STAGE_META.items():
            if not meta.get("required", False):
                continue
            status = summary.get(stage, {}).get("status")
            if not _stage_ready(status):
                ready = False
                break

        required_stages = [stage for stage, meta in _ONBOARDING_STAGE_META.items() if meta.get("required", False)]
        required_complete = [stage for stage in required_stages if _stage_ready(summary.get(stage, {}).get("status"))]
        pending_required = [
            stage for stage in required_stages if not _stage_ready(summary.get(stage, {}).get("status"))
        ]
        optional_stages = [stage for stage in summary if stage not in required_stages]
        optional_complete = [stage for stage in optional_stages if _stage_ready(summary.get(stage, {}).get("status"))]
        status_counts: dict[str, int] = {}
        for info in summary.values():
            status_value = str(info.get("status", "unknown"))
            status_counts[status_value] = status_counts.get(status_value, 0) + 1

        progress = round(len(required_complete) / len(required_stages), 4) if required_stages else 1.0

        warning_details = {stage: list(messages) for stage, messages in self._warnings.items() if messages}

        metrics = {
            "required_total": len(required_stages),
            "required_complete": len(required_complete),
            "required_remaining": len(pending_required),
            "completed_required": list(required_complete),
            "pending_required": list(pending_required),
            "optional_total": len(optional_stages),
            "optional_complete": len(optional_complete),
            "progress": progress,
            "next_required_stage": pending_required[0] if pending_required else None,
            "next_required_label": summary.get(pending_required[0], {}).get("label") if pending_required else None,
            "status_counts": status_counts,
            "blocked": list(blocked),
            "warnings_total": len(warnings),
            "warnings": list(warnings),
        }
        if warning_details:
            metrics["warning_details"] = warning_details

        metrics_copy = dict(metrics)

        timeline_snapshot = list(self._timeline)

        payload = {
            "order": list(_ONBOARDING_STAGE_ORDER),
            "stages": summary,
            "failures": failures,
            "skipped": skipped,
            "blocked": blocked,
            "warnings": warnings,
            "ready": ready,
            "metrics": metrics_copy,
            "timeline": timeline_snapshot,
        }
        if warning_details:
            payload["warning_details"] = warning_details

        self.entry_data["onboarding_status"] = payload
        self.entry_data["onboarding_ready"] = ready
        self.entry_data["onboarding_metrics"] = dict(metrics_copy)
        snapshot = {
            "completed_at": _utcnow(),
            "ready": ready,
            "failures": list(failures),
            "skipped": list(skipped),
            "blocked": list(blocked),
            "warnings": list(warnings),
            "stages": {stage: info.get("status") for stage, info in summary.items()},
            "attempts": {
                stage: {
                    key: value
                    for key, value in self._state.get(stage, {}).items()
                    if key
                    in {
                        "attempts",
                        "last_status",
                        "last_success",
                        "last_failure",
                        "last_duration",
                        "last_warning",
                    }
                }
                for stage in summary
            },
            "metrics": dict(metrics_copy),
            "timeline": timeline_snapshot,
        }
        if warning_details:
            snapshot["warning_details"] = warning_details
        self._history.append(snapshot)
        if len(self._history) > 5:
            del self._history[:-5]
        self.entry_data["onboarding_history"] = self._history
        self.entry_data["onboarding_last_completed"] = snapshot["completed_at"]
        self._sync_entry_warnings()
        return payload


def _record_onboarding_error(
    hass: HomeAssistant,
    entry: ConfigEntry,
    entry_data: dict[str, Any],
    stage: str,
    err: Exception,
) -> None:
    message = str(err) or err.__class__.__name__
    errors = entry_data.setdefault("onboarding_errors", {})
    errors[stage] = {
        "stage": stage,
        "label": _stage_label(stage),
        "error": message,
        "exception": repr(err),
    }
    severity = getattr(ir.IssueSeverity, "ERROR", getattr(ir.IssueSeverity, "WARNING", "error"))
    issue_id = _stage_issue_id(entry.entry_id, stage)
    try:
        ir.async_create_issue(
            hass,
            DOMAIN,
            issue_id,
            is_fixable=False,
            severity=severity,
            translation_key="onboarding_stage_failure",
            translation_placeholders={
                "stage": _stage_label(stage),
                "error": message,
            },
        )
    except Exception:  # pragma: no cover - issue registry best-effort
        _LOGGER.debug("Failed to create onboarding issue %s", issue_id)


def _clear_onboarding_error(hass: HomeAssistant, entry: ConfigEntry, entry_data: dict[str, Any], stage: str) -> None:
    errors = entry_data.get("onboarding_errors")
    if isinstance(errors, dict) and stage in errors:
        errors.pop(stage, None)
        if not errors:
            entry_data.pop("onboarding_errors", None)
    issue_id = _stage_issue_id(entry.entry_id, stage)
    try:
        ir.async_delete_issue(hass, DOMAIN, issue_id)
    except Exception:  # pragma: no cover - best-effort cleanup
        _LOGGER.debug("Failed to clear onboarding issue %s", issue_id)


def _clear_all_onboarding_errors(hass: HomeAssistant, entry: ConfigEntry, entry_data: dict[str, Any]) -> None:
    errors = entry_data.get("onboarding_errors")
    if not isinstance(errors, dict):
        return
    for stage in list(errors):
        _clear_onboarding_error(hass, entry, entry_data, stage)


async def async_setup(_hass: HomeAssistant, _config: dict) -> bool:
    """Set up the integration using YAML is not supported."""

    _LOGGER.debug("async_setup called: configuration entries only")
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Horticulture Assistant from a ConfigEntry."""

    domain_data = hass.data.setdefault(DOMAIN, {})
    entry_data = domain_data.setdefault(entry.entry_id, {"config_entry": entry})
    entry_data.setdefault("onboarding_errors", {})
    manager = _OnboardingManager(hass, entry, entry_data)

    paths_ready, _ = await manager.guard_async("local_paths", ensure_local_data_paths(hass))

    dataset_reason = None
    dataset_dependencies = None
    if not paths_ready:
        dataset_reason = "local data paths unavailable"
        dataset_dependencies = ("local_paths",)

    dataset_ready = False
    if (
        manager.ensure_dependencies(
            "dataset_health",
            reason=dataset_reason,
            dependencies=dataset_dependencies,
        )
        and paths_ready
    ):
        dataset_ready, _ = await manager.guard_async("dataset_health", async_setup_dataset_health(hass))

    existing_errors = dict(entry_data.get("onboarding_errors", {}))
    existing_state = entry_data.get("onboarding_stage_state")
    if not isinstance(existing_state, dict):
        existing_state = {}
    existing_history = entry_data.get("onboarding_history")
    if not isinstance(existing_history, list):
        existing_history = []
    existing_timeline = entry_data.get("onboarding_timeline")
    if not isinstance(existing_timeline, list):
        existing_timeline = []
    last_completed = entry_data.get("onboarding_last_completed")

    entry_data = await store_entry_data(hass, entry)
    entry_data["onboarding_stage_state"] = existing_state
    entry_data["onboarding_history"] = existing_history
    entry_data["onboarding_timeline"] = existing_timeline
    if last_completed:
        entry_data["onboarding_last_completed"] = last_completed
    manager.rebind(entry_data)
    if existing_errors:
        entry_data["onboarding_errors"] = existing_errors
    else:
        entry_data.setdefault("onboarding_errors", {})

    ensure_snapshot: Mapping[str, Any] | None = None
    snapshot_candidate = entry_data.get("snapshot")
    if isinstance(snapshot_candidate, Mapping):
        profiles_snapshot = snapshot_candidate.get("profiles")
        primary_profile_id = snapshot_candidate.get("primary_profile_id")
        if (isinstance(profiles_snapshot, Mapping) and profiles_snapshot) or primary_profile_id:
            ensure_snapshot = snapshot_candidate

    ensure_profiles: Mapping[str, Any] | None = None
    raw_profiles = entry.options.get(CONF_PROFILES)
    if isinstance(raw_profiles, Mapping) and raw_profiles:
        ensure_profiles = raw_profiles

    if ensure_snapshot or ensure_profiles:
        try:
            await ensure_all_profile_devices_registered(
                hass,
                entry,
                snapshot=ensure_snapshot,
                extra_profiles=ensure_profiles,
            )
        except Exception as err:  # pragma: no cover - defensive logging
            _LOGGER.debug(
                "Unable to pre-synchronise profile devices for '%s' during setup: %s",
                getattr(entry, "entry_id", "unknown"),
                err,
            )
        else:
            manager.rebind(entry_data)

    base_url = entry.options.get(CONF_BASE_URL, entry.data.get(CONF_BASE_URL, DEFAULT_BASE_URL))
    api_key = entry.options.get(CONF_API_KEY, entry.data.get(CONF_API_KEY, ""))
    model = entry.options.get(CONF_MODEL, entry.data.get(CONF_MODEL, DEFAULT_MODEL))
    keep_stale = entry.options.get(CONF_KEEP_STALE, entry.data.get(CONF_KEEP_STALE, DEFAULT_KEEP_STALE))
    update_minutes_raw = entry.options.get(
        CONF_UPDATE_INTERVAL,
        entry.data.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_MINUTES),
    )
    update_minutes = _normalise_update_minutes(update_minutes_raw)

    api = ChatApi(hass, api_key, base_url, model)

    local_store = LocalStore(hass)
    local_store_reason = None
    local_store_dependencies = None
    if not paths_ready:
        local_store_reason = "local data paths unavailable"
        local_store_dependencies = ("local_paths",)

    local_store_ready = False
    if (
        manager.ensure_dependencies(
            "local_store",
            reason=local_store_reason,
            dependencies=local_store_dependencies,
        )
        and paths_ready
    ):
        local_store_ready, _ = await manager.guard_async("local_store", local_store.load())
    if not local_store_ready and local_store.data is None:
        local_store.data = deepcopy(DEFAULT_DATA)

    profile_store: ProfileStore | None = ProfileStore(hass)
    profile_store_reason = None
    if not local_store_ready:
        profile_store_reason = "local store unavailable"

    profile_store_ready = False
    if (
        manager.ensure_dependencies(
            "profile_store",
            reason=profile_store_reason,
        )
        and local_store_ready
    ):
        profile_store_ready, _ = await manager.guard_async("profile_store", profile_store.async_init())
    if not profile_store_ready:
        profile_store = None

    cloud_sync_manager = CloudSyncManager(hass, entry)

    profile_registry: ProfileRegistry | None = ProfileRegistry(hass, entry)
    registry_reason = None
    if not profile_store_ready:
        registry_reason = "profile store unavailable"

    profile_registry_ready = False
    if (
        manager.ensure_dependencies(
            "profile_registry",
            reason=registry_reason,
        )
        and profile_store_ready
    ):
        profile_registry_ready, _ = await manager.guard_async("profile_registry", profile_registry.async_initialize())
    cloud_publisher = CloudSyncPublisher(cloud_sync_manager, entry.entry_id)
    if profile_registry_ready and profile_registry is not None:
        profile_registry.attach_cloud_publisher(cloud_publisher)
    elif not profile_registry_ready:
        profile_registry = None

    registry_warnings: list[str] = []
    if profile_registry_ready and profile_registry is not None:
        try:
            registry_warnings = profile_registry.collect_onboarding_warnings()
        except Exception:  # pragma: no cover - defensive guard
            registry_warnings = []
        for warning in registry_warnings:
            manager.record_warning("profile_registry", warning)
    if registry_warnings:
        entry_data["profile_registry_warnings"] = registry_warnings
    else:
        entry_data.pop("profile_registry_warnings", None)

    coordinator = HorticultureCoordinator(hass, entry)
    coordinator_reason = None
    if not local_store_ready:
        coordinator_reason = "local store unavailable"

    coordinator_ready = False
    if (
        manager.ensure_dependencies(
            "coordinator_refresh",
            reason=coordinator_reason,
        )
        and local_store_ready
    ):
        coordinator_ready, _ = await manager.guard_async(
            "coordinator_refresh", coordinator.async_config_entry_first_refresh()
        )

    ai_coordinator = HortiAICoordinator(
        hass,
        api,
        local_store,
        update_minutes,
        (local_store.data or {}).get("recommendation") if local_store.data else None,
    )
    ai_ready = False
    ai_dependencies = ("local_store",) if not local_store_ready else None
    ai_reason = "local store unavailable" if not local_store_ready else None
    if manager.ensure_dependencies("coordinator_ai_refresh", reason=ai_reason, dependencies=ai_dependencies):
        ai_ready, _ = await manager.guard_async(
            "coordinator_ai_refresh", ai_coordinator.async_config_entry_first_refresh()
        )
    local_coordinator = HortiLocalCoordinator(
        hass,
        local_store,
        update_minutes,
    )
    local_ready = False
    local_dependencies = ("local_store",) if not local_store_ready else None
    local_reason = "local store unavailable" if not local_store_ready else None
    if manager.ensure_dependencies("coordinator_local_refresh", reason=local_reason, dependencies=local_dependencies):
        local_ready, _ = await manager.guard_async(
            "coordinator_local_refresh", local_coordinator.async_config_entry_first_refresh()
        )

    entry_data["dataset_monitor_attached"] = dataset_ready
    entry_data.update(
        {
            "api": api,
            "profile_store": profile_store,
            "profile_store_ready": profile_store_ready,
            "profile_registry": profile_registry,
            "profile_registry_ready": profile_registry_ready,
            "profiles": profile_registry,
            "registry": profile_registry,
            "local_store": local_store,
            "local_store_ready": local_store_ready,
            "local_paths_ready": paths_ready,
            "coordinator": coordinator,
            "coordinator_ready": coordinator_ready,
            "coordinator_ai": ai_coordinator,
            "coordinator_ai_ready": ai_ready,
            "coordinator_local": local_coordinator,
            "coordinator_local_ready": local_ready,
            "keep_stale": keep_stale,
            "cloud_sync_manager": cloud_sync_manager,
            "cloud_publisher": cloud_publisher,
        }
    )
    http_ready, _ = await manager.guard_call("http_views", async_register_http_views, hass)
    entry_data["http_views_registered"] = http_ready

    cloud_reason = None
    cloud_dependencies = None
    if profile_registry is None:
        cloud_reason = "profile registry unavailable"
        cloud_dependencies = ("profile_registry",)
    elif not profile_registry_ready:
        cloud_reason = "profile registry not ready"
        cloud_dependencies = ("profile_registry",)

    cloud_sync_ready = False
    if (
        manager.ensure_dependencies(
            "cloud_sync",
            reason=cloud_reason,
            dependencies=cloud_dependencies,
        )
        and profile_registry is not None
        and profile_registry_ready
    ):
        cloud_sync_ready, _ = await manager.guard_async("cloud_sync", cloud_sync_manager.async_start())
    entry_data["cloud_sync_ready"] = cloud_sync_ready
    cloud_status = cloud_sync_manager.status()
    entry_data["cloud_sync_status"] = cloud_status
    if cloud_sync_ready:
        reason_parts: list[str] = []
        if not cloud_status.get("configured", True):
            reason_parts.append("configuration incomplete")
        if not cloud_status.get("enabled", True):
            reason_parts.append("disabled in options")
        if reason_parts:
            summary = " and ".join(reason_parts)
            manager.record_warning("cloud_sync", f"Cloud sync {summary}")

    if profile_registry is not None:
        domain_data["registry"] = profile_registry
    else:
        domain_data.pop("registry", None)

    def _ensure_profile_entities(config_entry: ConfigEntry) -> None:
        primary_sensors = get_primary_profile_sensors(config_entry)
        if primary_sensors:
            sensor_ids = [value for value in primary_sensors.values() if isinstance(value, str)]
            if sensor_ids:
                ensure_entities_exist(
                    hass,
                    config_entry.options.get(CONF_PLANT_ID)
                    or config_entry.data.get(CONF_PLANT_ID)
                    or config_entry.entry_id,
                    sensor_ids,
                )

        profile_options = config_entry.options.get(CONF_PROFILES, {})
        if isinstance(profile_options, dict):
            for profile_id, profile_data in profile_options.items():
                sensor_map = {}
                if isinstance(profile_data, dict):
                    raw = profile_data.get("sensors", {})
                    if isinstance(raw, dict):
                        sensor_map = raw
                if not sensor_map:
                    continue
                profile_sensors = [value for value in sensor_map.values() if isinstance(value, str)]
                if not profile_sensors:
                    continue
                ensure_entities_exist(
                    hass,
                    profile_id,
                    profile_sensors,
                    placeholders={
                        "plant_id": profile_id,
                        "profile_name": profile_data.get("name", profile_id)
                        if isinstance(profile_data, dict)
                        else profile_id,
                    },
                )

    entity_dependencies: list[str] = []
    entity_reasons: list[str] = []
    if profile_registry is None:
        entity_dependencies.append("profile_registry")
        entity_reasons.append("profile registry unavailable")
    elif not profile_registry_ready:
        entity_dependencies.append("profile_registry")
        entity_reasons.append("profile registry not ready")
    if not coordinator_ready:
        entity_dependencies.append("coordinator_refresh")
        entity_reasons.append("coordinator refresh not ready")

    entity_validation_ready = False
    if (
        manager.ensure_dependencies(
            "entity_validation",
            reason=", ".join(entity_reasons) if entity_reasons else None,
            dependencies=tuple(dict.fromkeys(entity_dependencies)) if entity_dependencies else None,
        )
        and profile_registry is not None
        and profile_registry_ready
        and coordinator_ready
    ):
        entity_validation_ready, _ = await manager.guard_call("entity_validation", _ensure_profile_entities, entry)
    entry_data["entity_validation_ready"] = entity_validation_ready

    service_dependencies: list[str] = []
    service_reasons: list[str] = []
    if profile_registry is None:
        service_dependencies.append("profile_registry")
        service_reasons.append("profile registry unavailable")
    elif not profile_registry_ready:
        service_dependencies.append("profile_registry")
        service_reasons.append("profile registry not ready")
    if not coordinator_ready:
        service_dependencies.append("coordinator_refresh")
        service_reasons.append("coordinator refresh not ready")

    services_ready = False
    if (
        manager.ensure_dependencies(
            "service_registration",
            reason=", ".join(service_reasons) if service_reasons else None,
            dependencies=tuple(dict.fromkeys(service_dependencies)) if service_dependencies else None,
        )
        and profile_registry is not None
        and profile_registry_ready
        and coordinator_ready
    ):
        services_ready, _ = await manager.guard_async(
            "service_registration",
            ha_services.async_register_all(
                hass,
                entry,
                ai_coordinator,
                local_coordinator,
                coordinator,
                profile_registry,
                local_store,
                cloud_manager=cloud_sync_manager,
            ),
        )
    entry_data["service_registration_ready"] = services_ready

    service_setup_ready = False
    if (
        manager.ensure_dependencies(
            "service_setup",
            reason="service registration incomplete" if not services_ready else None,
        )
        and services_ready
    ):
        service_setup_ready, _ = await manager.guard_call("service_setup", ha_services.async_setup_services, hass)
    entry_data["service_setup_ready"] = service_setup_ready

    calibration_ready = False
    if (
        manager.ensure_dependencies(
            "calibration_services",
            reason="service registration incomplete" if not services_ready else None,
        )
        and services_ready
    ):
        if calibration_services is not None and hasattr(calibration_services, "async_setup_services"):
            calibration_ready, _ = await manager.guard_call(
                "calibration_services",
                calibration_services.async_setup_services,
                hass,
            )
        else:
            calibration_ready, _ = manager.skip("calibration_services", "calibration services unavailable")
    entry_data["calibration_services_ready"] = calibration_ready

    platform_ready = False
    platform_dependencies_ready = manager.ensure_dependencies(
        "platform_setup",
        reason="service registration incomplete" if not services_ready else None,
    )
    if platform_dependencies_ready and services_ready:
        forward_setups = getattr(hass.config_entries, "async_forward_entry_setups", None)
        legacy_forward = getattr(hass.config_entries, "async_forward_entry_setup", None)

        if callable(forward_setups) or callable(legacy_forward):
            platform_ready, _ = await manager.guard_async(
                "platform_setup",
                _async_forward_entry_platforms(hass, entry),
            )
        else:
            platform_ready, _ = manager.skip("platform_setup", "platform loader unavailable")

    entry_data["platform_setup_ready"] = platform_ready

    async def _async_entry_updated(hass: HomeAssistant, updated_entry: ConfigEntry) -> None:
        nonlocal entry_data

        def _profile_id_set(value: Any) -> set[str]:
            """Return a normalised set of profile identifiers from ``value``."""

            items: set[str] = set()
            if isinstance(value, Mapping):
                iterator = value.keys()
            elif isinstance(value, list | tuple | set):
                iterator = value
            elif value is None:
                iterator = ()
            else:
                iterator = (value,)

            for item in iterator:
                if isinstance(item, str):
                    text = item.strip()
                else:
                    if item is None:
                        continue
                    text = str(item).strip()
                if text:
                    items.add(text)

            return items

        previous_profile_ids: set[str] = set()
        if isinstance(entry_data, Mapping):
            previous_profile_ids = _profile_id_set(entry_data.get("profile_ids"))
        previous_context_ids = previous_profile_ids.copy()

        try:
            refreshed_raw = await update_entry_data(hass, updated_entry)
        except Exception as err:  # pragma: no cover - defensive fallback
            _LOGGER.debug(
                "Unable to refresh entry data for '%s' during update: %s",
                getattr(updated_entry, "entry_id", "unknown"),
                err,
            )
            refreshed_raw = get_entry_data(hass, updated_entry)
            await backfill_profile_devices_from_options(hass, updated_entry, refreshed_raw)
            refreshed_raw = get_entry_data(hass, updated_entry) or refreshed_raw
        else:
            if await backfill_profile_devices_from_options(hass, updated_entry, refreshed_raw):
                refreshed_raw = get_entry_data(hass, updated_entry) or refreshed_raw

        ensure_snapshot: Mapping[str, Any] | None = None
        if isinstance(refreshed_raw, Mapping):
            snapshot_candidate = refreshed_raw.get("snapshot")
            if isinstance(snapshot_candidate, Mapping):
                ensure_snapshot = snapshot_candidate

        ensure_profiles: Mapping[str, Any] | None = None
        raw_profiles = updated_entry.options.get(CONF_PROFILES)
        if isinstance(raw_profiles, Mapping) and raw_profiles:
            ensure_profiles = raw_profiles

        refreshed_via_ensure = False
        if ensure_snapshot or ensure_profiles:
            try:
                await ensure_all_profile_devices_registered(
                    hass,
                    updated_entry,
                    snapshot=ensure_snapshot,
                    extra_profiles=ensure_profiles,
                )
            except Exception:  # pragma: no cover - defensive safeguard
                pass
            else:
                refreshed_via_ensure = True

        if refreshed_via_ensure:
            latest_entry_data = get_entry_data(hass, updated_entry)
            if isinstance(latest_entry_data, Mapping):
                refreshed_raw = latest_entry_data

        refreshed = dict(refreshed_raw) if isinstance(refreshed_raw, Mapping) else {"config_entry": updated_entry}

        refreshed.setdefault("config_entry", updated_entry)
        refreshed.setdefault("onboarding_errors", entry_data.get("onboarding_errors", {}))
        refreshed["keep_stale"] = updated_entry.options.get(
            CONF_KEEP_STALE,
            updated_entry.data.get(CONF_KEEP_STALE, DEFAULT_KEEP_STALE),
        )
        coordinator.update_from_entry(updated_entry)
        refreshed["cloud_sync_status"] = cloud_sync_manager.status()
        validation_ready, _ = await manager.guard_call("entity_validation", _ensure_profile_entities, updated_entry)
        refreshed["entity_validation_ready"] = validation_ready

        new_profile_ids = _profile_id_set(refreshed.get("profile_ids"))
        entry_data = refreshed
        manager.rebind(entry_data)

        added_ids = tuple(sorted(new_profile_ids - previous_context_ids))
        removed_ids = tuple(sorted(previous_context_ids - new_profile_ids))
        if added_ids or removed_ids:
            async_dispatcher_send(
                hass,
                signal_profile_contexts_updated(updated_entry.entry_id),
                {"added": added_ids, "removed": removed_ids},
            )

    unsubscribe = None
    listener_success = False
    update_listener_ready = manager.ensure_dependencies(
        "update_listener",
        reason="platform setup incomplete" if not platform_ready else None,
    )
    if update_listener_ready and platform_ready:
        if hasattr(entry, "add_update_listener"):

            def _add_listener():
                try:
                    return entry.add_update_listener(hass, _async_entry_updated)
                except TypeError:
                    return entry.add_update_listener(_async_entry_updated)

            listener_success, unsubscribe = await manager.guard_call("update_listener", _add_listener)
            if listener_success and unsubscribe and hasattr(entry, "async_on_unload"):
                await manager.guard_call("update_listener", entry.async_on_unload, unsubscribe)
        else:
            listener_success, unsubscribe = manager.skip("update_listener", "config entry cannot register listeners")
    entry_data["update_listener_registered"] = listener_success
    if unsubscribe is not None:
        entry_data["update_listener_unsub"] = unsubscribe
    else:
        entry_data.pop("update_listener_unsub", None)

    manager.finalise()

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a ConfigEntry."""

    unload_platforms = getattr(hass.config_entries, "async_unload_platforms", None)
    legacy_unload = getattr(hass.config_entries, "async_forward_entry_unload", None)

    if callable(unload_platforms):
        unload_ok = await unload_platforms(entry, PLATFORMS)
    elif callable(legacy_unload):
        results = await asyncio.gather(
            *(legacy_unload(entry, platform) for platform in PLATFORMS),
            return_exceptions=True,
        )
        unload_ok = all(result is True for result in results)
    else:
        unload_ok = False

    if unload_ok:
        data = hass.data.get(DOMAIN, {})
        info = data.pop(entry.entry_id, None)
        if info:
            _clear_all_onboarding_errors(hass, entry, info)
            if info.get("dataset_monitor_attached"):
                await async_release_dataset_health(hass)
            manager = info.get("cloud_sync_manager")
            if manager and hasattr(manager, "async_stop"):
                with contextlib.suppress(Exception):
                    await manager.async_stop()
            for coord in (
                info.get("coordinator"),
                info.get("coordinator_ai"),
                info.get("coordinator_local"),
            ):
                if coord and hasattr(coord, "async_shutdown"):
                    with contextlib.suppress(Exception):
                        await coord.async_shutdown()
            profiles = info.get("profiles")
            if profiles and hasattr(profiles, "async_unload"):
                with contextlib.suppress(Exception):
                    await profiles.async_unload()

        registry = data.get("registry")
        profile_registry = info.get("profile_registry") if info else None
        if registry is not None and registry is profile_registry:
            data.pop("registry", None)

        if not data:
            hass.data.pop(DOMAIN, None)
        remove_entry_data(hass, entry.entry_id)
    return unload_ok


def _coerce_dict(value: Any) -> dict[str, Any]:
    """Return ``value`` coerced into a mutable dictionary."""

    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, Mapping):
        return {str(key): item for key, item in value.items()}
    return {}


def _coerce_sensor_map(value: Any) -> dict[str, str]:
    """Return a mapping of sensor roles to entity ids."""

    sensors: dict[str, str] = {}
    for key, item in _coerce_dict(value).items():
        if isinstance(item, str) and item:
            sensors[str(key)] = item
    return sensors


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate config entry to the latest version."""

    data: dict[str, Any] = dict(entry.data)
    options: dict[str, Any] = dict(entry.options)
    migrated = False

    if entry.version < 2:
        migrated = True
        entry.version = 2
        if CONF_UPDATE_INTERVAL in data:
            options.setdefault(CONF_UPDATE_INTERVAL, data.pop(CONF_UPDATE_INTERVAL))
        options.setdefault(CONF_KEEP_STALE, data.pop(CONF_KEEP_STALE, DEFAULT_KEEP_STALE))

    if entry.version < 3:
        migrated = True
        entry.version = 3

        temp_entry = SimpleNamespace(
            data=data,
            options=options,
            entry_id=getattr(entry, "entry_id", DOMAIN),
        )
        derived_id, derived_name = get_entry_plant_info(temp_entry)
        plant_id = get_primary_profile_id(temp_entry) or derived_id or getattr(entry, "entry_id", DOMAIN)
        if not plant_id:
            plant_id = getattr(entry, "entry_id", DOMAIN)
        plant_name = derived_name or data.get(CONF_PLANT_NAME) or entry.title or plant_id

        raw_profiles = options.get(CONF_PROFILES)
        profiles: dict[str, dict[str, Any]] = {}
        if isinstance(raw_profiles, Mapping):
            for pid, payload in raw_profiles.items():
                if not isinstance(pid, str) or not pid:
                    continue
                profiles[pid] = _coerce_dict(payload)

        sensors_map = _coerce_sensor_map(options.get("sensors"))
        if not sensors_map:
            general_section = options.get("general")
            if isinstance(general_section, Mapping):
                sensors_map = _coerce_sensor_map(general_section.get("sensors"))

        thresholds_map = _coerce_dict(options.get("thresholds"))
        resolved_map = _coerce_dict(options.get("resolved_targets"))
        variables_map = _coerce_dict(options.get("variables"))
        sources_map = _coerce_dict(options.get("sources"))
        citations_map = _coerce_dict(options.get("citations"))

        base_profile = _coerce_dict(profiles.get(plant_id))
        display_name = base_profile.get("name")
        if not isinstance(display_name, str) or not display_name.strip():
            display_name = plant_name
        base_profile["name"] = display_name
        base_profile.setdefault("display_name", display_name)
        base_profile["plant_id"] = plant_id
        base_profile["profile_id"] = plant_id

        existing_sensors = _coerce_sensor_map(base_profile.get("sensors"))
        existing_sensors.update(sensors_map)
        if existing_sensors:
            base_profile["sensors"] = existing_sensors

        plant_type = data.get(CONF_PLANT_TYPE)
        general_map = _coerce_dict(base_profile.get("general"))
        general_sensors = _coerce_sensor_map(general_map.get("sensors"))
        general_sensors.update(existing_sensors)
        if general_sensors:
            general_map["sensors"] = general_sensors
        if isinstance(plant_type, str) and plant_type:
            general_map.setdefault("plant_type", plant_type)
        scope_value = general_map.get(CONF_PROFILE_SCOPE) or base_profile.get(CONF_PROFILE_SCOPE)
        if not scope_value:
            scope_value = PROFILE_SCOPE_DEFAULT
        general_map[CONF_PROFILE_SCOPE] = scope_value
        base_profile["general"] = general_map

        thresholds_payload = {
            "thresholds": _coerce_dict(base_profile.get("thresholds")),
            "resolved_targets": _coerce_dict(base_profile.get("resolved_targets")),
            "variables": _coerce_dict(base_profile.get("variables")),
        }
        if thresholds_map:
            thresholds_payload["thresholds"].update(thresholds_map)
        if resolved_map:
            thresholds_payload["resolved_targets"].update(resolved_map)
        if variables_map:
            thresholds_payload["variables"].update(variables_map)
        if thresholds_payload["thresholds"] and (
            not thresholds_payload["resolved_targets"] or not thresholds_payload["variables"]
        ):
            sync_thresholds(thresholds_payload, default_source="imported")

    if thresholds_payload["thresholds"]:
        base_profile["thresholds"] = thresholds_payload["thresholds"]
    else:
        base_profile.pop("thresholds", None)
        if thresholds_payload["resolved_targets"]:
            base_profile["resolved_targets"] = thresholds_payload["resolved_targets"]
        else:
            base_profile.pop("resolved_targets", None)
        if thresholds_payload["variables"]:
            base_profile["variables"] = thresholds_payload["variables"]
        else:
            base_profile.pop("variables", None)

        existing_sources = _coerce_dict(base_profile.get("sources"))
        if sources_map:
            existing_sources.update(sources_map)
        if existing_sources:
            base_profile["sources"] = existing_sources

        existing_citations = _coerce_dict(base_profile.get("citations"))
        if citations_map:
            existing_citations.update(citations_map)
        if existing_citations:
            base_profile["citations"] = existing_citations

        for key in ("image_url", "species_display", "species_pid", "opb_credentials"):
            value = options.get(key)
            if value is not None and key not in base_profile:
                base_profile[key] = value

        profiles[plant_id] = base_profile

        normalised_profiles: dict[str, dict[str, Any]] = {}
        for pid, payload in profiles.items():
            prof = _coerce_dict(payload)
            prof.setdefault("plant_id", pid)
            prof.setdefault("profile_id", pid)
            name = prof.get("name") or prof.get("display_name") or pid
            if not isinstance(name, str):
                name = str(name)
            prof["name"] = name
            prof.setdefault("display_name", name)
            general = _coerce_dict(prof.get("general"))
            general_sensors = _coerce_sensor_map(general.get("sensors"))
            profile_sensors = _coerce_sensor_map(prof.get("sensors"))
            if profile_sensors:
                general_sensors.update(profile_sensors)
            if general_sensors:
                general["sensors"] = general_sensors
            if pid == plant_id and isinstance(plant_type, str) and plant_type:
                general.setdefault("plant_type", plant_type)
            if not general.get(CONF_PROFILE_SCOPE):
                general[CONF_PROFILE_SCOPE] = PROFILE_SCOPE_DEFAULT
            prof["general"] = general
            ensure_sections(prof, plant_id=pid, display_name=name)
            normalised_profiles[pid] = prof

        profiles = normalised_profiles
        options[CONF_PROFILES] = profiles

        primary_profile = profiles[plant_id]
        sensors_out = _coerce_sensor_map(primary_profile.get("sensors"))
        if sensors_out:
            options["sensors"] = sensors_out
        elif "sensors" in options:
            options.pop("sensors", None)

        for key in ("thresholds", "resolved_targets", "variables", "sources", "citations"):
            value = _coerce_dict(primary_profile.get(key))
            if value:
                options[key] = value
            else:
                options.pop(key, None)

        data.setdefault(CONF_PLANT_ID, plant_id)
        if isinstance(plant_name, str) and plant_name:
            data.setdefault(CONF_PLANT_NAME, plant_name)

    if entry.version < 4:
        migrated = True
        entry.version = 4

        entry_prefix = f"{entry.entry_id}_"
        entity_registry = er.async_get(hass)
        for item in er.async_entries_for_config_entry(entity_registry, entry.entry_id):
            unique_id = getattr(item, "unique_id", None)
            if not unique_id or not isinstance(unique_id, str):
                continue
            if unique_id.startswith(entry_prefix):
                continue
            entity_registry.async_update_entity(item.entity_id, unique_id=f"{entry_prefix}{unique_id}")

    if migrated:
        hass.config_entries.async_update_entry(entry, data=data, options=options)

    return True
