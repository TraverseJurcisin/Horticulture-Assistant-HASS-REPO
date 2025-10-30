"""In-memory registry for managing plant profiles.

This module centralizes profile operations such as loading from storage,
updating sensors, refreshing species data and exporting the profile
collection.  Having a registry makes it easier for services and diagnostics
modules to reason about the set of configured plants without each feature
needing to parse config entry options or storage files individually.
"""

from __future__ import annotations

import asyncio
import hashlib
import inspect
import json
import logging
from collections.abc import Callable, Iterable, Mapping, Sequence, Set
from copy import deepcopy
from datetime import datetime, timezone
from math import isfinite
from pathlib import Path
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.util import slugify

from .cloudsync.publisher import CloudSyncPublisher
from .const import (
    CONF_PROFILE_SCOPE,
    CONF_PROFILES,
    DOMAIN,
    EVENT_PROFILE_CULTIVATION_RECORDED,
    EVENT_PROFILE_HARVEST_RECORDED,
    EVENT_PROFILE_NUTRIENT_RECORDED,
    EVENT_PROFILE_RUN_RECORDED,
    ISSUE_PROFILE_VALIDATION_PREFIX,
    NOTIFICATION_PROFILE_LINEAGE,
    NOTIFICATION_PROFILE_VALIDATION,
    PROFILE_SCOPE_CHOICES,
    PROFILE_SCOPE_DEFAULT,
)
from .history import HistoryExporter
from .profile.compat import sync_thresholds
from .profile.options import options_profile_to_dataclass
from .profile.schema import (
    BioProfile,
    ComputedStatSnapshot,
    CultivationEvent,
    HarvestEvent,
    NutrientApplication,
    ResolvedTarget,
    RunEvent,
)
from .profile.statistics import recompute_statistics
from .profile.store import CACHE_KEY as PROFILE_STORE_CACHE_KEY
from .profile.store import STORE_KEY as PROFILE_STORE_KEY
from .profile.store import STORE_VERSION as PROFILE_STORE_VERSION
from .profile.utils import (
    LineageLinkReport,
    ensure_sections,
    link_species_and_cultivars,
    sync_general_section,
)
from .profile.validation import evaluate_threshold_bounds
from .sensor_validation import collate_issue_messages, validate_sensor_links
from .utils.entry_helpers import (
    profile_device_identifier,
    resolve_profile_device_info,
    serialise_device_info,
)
from .validators import (
    validate_cultivation_event_dict,
    validate_harvest_event_dict,
    validate_nutrient_event_dict,
    validate_profile_dict,
    validate_run_event_dict,
)

try:  # pragma: no cover - Home Assistant not available in tests
    from homeassistant.helpers import issue_registry as ir
except (ImportError, ModuleNotFoundError):  # pragma: no cover - executed in CI tests
    import types
    from enum import Enum

    class IssueSeverity(str, Enum):
        WARNING = "warning"

    ir = types.SimpleNamespace(  # type: ignore[assignment]
        IssueSeverity=IssueSeverity,
        async_create_issue=lambda *_args, **_kwargs: None,
        async_delete_issue=lambda *_args, **_kwargs: None,
    )

_LOGGER = logging.getLogger(__name__)


def _parent_issue_id(profile_id: str, parent_id: str) -> str:
    """Return a deterministic, unique issue id for a missing parent link."""

    slug = slugify(parent_id) or "unknown_parent"
    digest = hashlib.sha1(parent_id.encode("utf-8", "ignore")).hexdigest()[:8]
    return f"missing_parent_{profile_id}_{slug}_{digest}"


def _species_issue_id(profile_id: str, species_id: str) -> str:
    """Return a deterministic issue id for a missing species reference."""

    slug = slugify(species_id) or "unknown_species"
    digest = hashlib.sha1(species_id.encode("utf-8", "ignore")).hexdigest()[:8]
    return f"missing_species_{profile_id}_{slug}_{digest}"


def _normalise_sensor_value(value: Any) -> str | list[str] | None:
    """Return a cleaned representation of a sensor mapping value."""

    if isinstance(value, str):
        entity_id = value.strip()
        return entity_id or None
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        items: list[str] = []
        for item in value:
            if isinstance(item, str):
                cleaned = item.strip()
            elif item is None:
                cleaned = ""
            else:
                cleaned = str(item).strip()
            if cleaned:
                items.append(cleaned)
        if items:
            return items
        return None
    return None


_SCHEMA_PATH = Path(__file__).parent / "data" / "schema" / "bio_profile.schema.json"
_PROFILE_SCHEMA: dict[str, Any] | None = None


def _load_profile_schema() -> dict[str, Any] | None:
    global _PROFILE_SCHEMA
    if _PROFILE_SCHEMA is None:
        try:
            text = _SCHEMA_PATH.read_text(encoding="utf-8")
            _PROFILE_SCHEMA = json.loads(text)
        except Exception as err:  # pragma: no cover - schema optional at runtime
            _LOGGER.debug("Unable to load profile schema: %s", err)
            _PROFILE_SCHEMA = None
    return _PROFILE_SCHEMA


STORAGE_VERSION = PROFILE_STORE_VERSION
STORAGE_KEY = PROFILE_STORE_KEY

UTC = getattr(datetime, "UTC", timezone.utc)  # type: ignore[attr-defined]  # noqa: UP017


class ProfileRegistry:
    """Maintain a collection of plant profiles for the integration."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self._store: Store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self._profiles: dict[str, BioProfile] = {}
        self._cloud_publisher: CloudSyncPublisher | None = None
        self._cloud_pending_snapshot = False
        self._missing_species_logged: set[tuple[str, str]] = set()
        self._missing_parents_logged: set[tuple[str, str]] = set()
        self._missing_species_issues: set[tuple[str, str]] = set()
        self._missing_parent_issues: set[tuple[str, str]] = set()
        self._validation_issues: dict[str, list[str]] = {}
        self._validation_dirty = False
        self._validation_digest: tuple[tuple[str, str], ...] | None = None
        self._validation_issue_keys: set[str] = set()
        self._validation_issue_summaries: dict[str, str] = {}
        self._lineage_missing_species: set[tuple[str, str]] = set()
        self._lineage_missing_parents: set[tuple[str, str]] = set()
        self._lineage_notification_dirty = False
        self._lineage_notification_digest: tuple[tuple[str, str, str], ...] | None = None
        self._history_exporter: HistoryExporter | None
        try:
            self._history_exporter = HistoryExporter(hass)
        except Exception as err:  # pragma: no cover - defensive guard
            _LOGGER.debug("History exporter disabled: %s", err)
            self._history_exporter = None

    def collect_onboarding_warnings(self) -> list[str]:
        """Return human-readable onboarding warnings for outstanding issues."""

        warnings: list[str] = []

        if self._missing_species_issues:
            affected = sorted({profile_id for profile_id, _ in self._missing_species_issues})
            sample = ", ".join(affected[:5])
            if len(affected) > 5:
                sample = f"{sample}, +{len(affected) - 5} more"
            warnings.append(f"missing species metadata for {sample}")

        if self._missing_parent_issues:
            affected = sorted({profile_id for profile_id, _ in self._missing_parent_issues})
            sample = ", ".join(affected[:5])
            if len(affected) > 5:
                sample = f"{sample}, +{len(affected) - 5} more"
            warnings.append(f"missing parent lineage for {sample}")

        if self._validation_issue_summaries:
            warnings.extend(sorted(self._validation_issue_summaries.values()))

        return warnings

    def _relink_profiles(self) -> None:
        if not self._profiles:
            self._log_lineage_warnings(LineageLinkReport())
            return

        report = link_species_and_cultivars(self._profiles.values())
        self._log_lineage_warnings(report)
        for profile in self._profiles.values():
            profile.refresh_sections()

    def _profile_device_metadata(
        self,
        profile_id: str,
        default_name: str | None = None,
    ) -> dict[str, Any]:
        """Return device metadata for ``profile_id`` suitable for diagnostics."""

        domain, identifier = profile_device_identifier(self.entry.entry_id, profile_id)
        info = resolve_profile_device_info(self.hass, self.entry.entry_id, profile_id)
        payload: dict[str, Any] = dict(info) if isinstance(info, Mapping) else {}

        identifier_tuple = (domain, identifier)
        identifiers_value = payload.get("identifiers")
        identifier_set: set[tuple[str, str]] = set()

        if isinstance(identifiers_value, Set):
            candidates: Iterable[Any] = identifiers_value
        elif isinstance(identifiers_value, list | tuple):
            candidates = identifiers_value
        else:
            candidates = ()

        for item in candidates:
            if isinstance(item, tuple) and len(item) == 2:
                identifier_set.add((str(item[0]), str(item[1])))

        if isinstance(identifiers_value, Mapping):
            for key, item in identifiers_value.items():
                if isinstance(item, tuple) and len(item) == 2:
                    identifier_set.add((str(item[0]), str(item[1])))
                elif isinstance(key, str):
                    identifier_set.add((str(key), str(item)))

        if identifier_tuple not in identifier_set:
            identifier_set.add(identifier_tuple)

        payload["identifiers"] = identifier_set
        name = payload.get("name")
        if not isinstance(name, str) or not name.strip():
            payload["name"] = default_name or profile_id
        manufacturer = payload.get("manufacturer")
        if not isinstance(manufacturer, str) or not manufacturer.strip():
            payload["manufacturer"] = "Horticulture Assistant"
        model = payload.get("model")
        if not isinstance(model, str) or not model.strip():
            payload["model"] = "Plant Profile"

        return {
            "identifier": {"domain": domain, "id": identifier},
            "info": serialise_device_info(payload),
        }

    @staticmethod
    def _merge_profile_data(stored: BioProfile, overlay: BioProfile) -> BioProfile:
        """Combine ``stored`` profile data with option ``overlay`` values."""

        merged = overlay

        def _is_empty(value: Any) -> bool:
            if value is None:
                return True
            if isinstance(value, (list | tuple | set | frozenset | dict)):
                return len(value) == 0
            if isinstance(value, str):
                return value.strip() == ""
            return False

        stored_general = dict(stored.general)
        overlay_general = dict(overlay.general)
        stored_sensors = dict(stored_general.get("sensors", {}))
        overlay_sensors = dict(overlay_general.get("sensors", {}))
        if stored_sensors or overlay_sensors:
            merged_sensors = dict(stored_sensors)
            merged_sensors.update(overlay_sensors)
            overlay_general["sensors"] = merged_sensors

        for key, value in stored_general.items():
            if key == "sensors":
                continue
            existing = overlay_general.get(key)
            if (key not in overlay_general or _is_empty(existing)) and not _is_empty(value):
                overlay_general[key] = deepcopy(value)

        merged.general = overlay_general
        merged.refresh_sections()

        def _merge_attr(name: str) -> None:
            stored_value = getattr(stored, name, None)
            overlay_value = getattr(merged, name, None)
            if _is_empty(overlay_value) and not _is_empty(stored_value):
                setattr(merged, name, deepcopy(stored_value))

        for field in (
            "parents",
            "identity",
            "taxonomy",
            "policies",
            "stable_knowledge",
            "lifecycle",
            "traits",
            "tags",
            "curated_targets",
            "diffs_vs_parent",
            "local_overrides",
            "resolver_state",
            "resolved_targets",
            "variables",
            "thresholds",
            "citations",
            "event_history",
            "run_history",
            "harvest_history",
            "nutrient_history",
            "statistics",
            "computed_stats",
            "local_metadata",
            "library_metadata",
            "last_resolved",
            "created_at",
            "updated_at",
        ):
            _merge_attr(field)

        merged.refresh_sections()
        return merged

    def _create_species_issue(
        self,
        profile_id: str,
        display_name: str,
        species_id: str,
    ) -> None:
        issue_key = (profile_id, species_id)
        if issue_key in self._missing_species_issues:
            return
        issue_id = _species_issue_id(profile_id, species_id)
        self._schedule_issue_result(
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                issue_id,
                is_fixable=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key="missing_lineage_species",
                translation_placeholders={
                    "profile_id": profile_id,
                    "profile_name": display_name,
                    "species_id": species_id,
                },
            )
        )
        self._missing_species_issues.add(issue_key)

    def _clear_species_issue(self, profile_id: str, species_id: str) -> None:
        issue_key = (profile_id, species_id)
        if issue_key not in self._missing_species_issues:
            return
        issue_id = _species_issue_id(profile_id, species_id)
        self._schedule_issue_result(
            ir.async_delete_issue(
                self.hass,
                DOMAIN,
                issue_id,
            )
        )
        self._missing_species_issues.discard(issue_key)

    def _create_parent_issue(
        self,
        profile_id: str,
        display_name: str,
        parent_id: str,
    ) -> None:
        issue_key = (profile_id, parent_id)
        if issue_key in self._missing_parent_issues:
            return
        self._schedule_issue_result(
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                _parent_issue_id(profile_id, parent_id),
                is_fixable=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key="missing_lineage_parent",
                translation_placeholders={
                    "profile_id": profile_id,
                    "profile_name": display_name,
                    "parent_id": parent_id,
                },
            )
        )
        self._missing_parent_issues.add(issue_key)

    def _clear_parent_issue(self, profile_id: str, parent_id: str) -> None:
        issue_key = (profile_id, parent_id)
        if issue_key not in self._missing_parent_issues:
            return
        self._schedule_issue_result(
            ir.async_delete_issue(
                self.hass,
                DOMAIN,
                _parent_issue_id(profile_id, parent_id),
            )
        )
        self._missing_parent_issues.discard(issue_key)

    def _create_validation_issue(self, profile: BioProfile, summary: str) -> None:
        issue_id = f"{ISSUE_PROFILE_VALIDATION_PREFIX}{profile.profile_id}"
        self._schedule_issue_result(
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                issue_id,
                is_fixable=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key="invalid_profile_schema",
                translation_placeholders={
                    "profile_id": profile.profile_id,
                    "profile_name": profile.display_name,
                    "issue_summary": summary,
                },
            )
        )
        self._validation_issue_keys.add(issue_id)
        self._validation_issue_summaries[profile.profile_id] = summary

    def _clear_validation_issue(self, profile_id: str) -> None:
        issue_id = f"{ISSUE_PROFILE_VALIDATION_PREFIX}{profile_id}"
        self._schedule_issue_result(
            ir.async_delete_issue(
                self.hass,
                DOMAIN,
                issue_id,
            )
        )
        self._validation_issue_keys.discard(issue_id)
        self._validation_issue_summaries.pop(profile_id, None)

    def _schedule_issue_result(self, result: Any) -> None:
        if result is None:
            return
        if inspect.isawaitable(result):
            scheduler = getattr(self.hass, "async_create_task", None)
            if callable(scheduler):
                scheduler(result)
            else:  # pragma: no cover - fallback when hass stub unavailable
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    loop = asyncio.get_event_loop()
                loop.create_task(result)

    def _sync_validation_issue(self, profile: BioProfile, issues: list[str]) -> None:
        if not issues:
            self._clear_validation_issue(profile.profile_id)
            return
        summary = str(issues[0])
        if len(issues) > 1:
            summary += f" (+{len(issues) - 1} more)"
        existing = self._validation_issue_summaries.get(profile.profile_id)
        if existing == summary:
            return
        self._create_validation_issue(profile, summary)

    def _log_lineage_warnings(self, report: LineageLinkReport | None) -> None:
        if report is None:
            return

        current_species: set[tuple[str, str]] = set()
        for profile_id, species_id in sorted(report.missing_species.items()):
            key = (profile_id, species_id)
            current_species.add(key)
            if key in self._missing_species_logged:
                continue
            profile = self._profiles.get(profile_id)
            display_name = profile.display_name if profile else profile_id
            _LOGGER.warning(
                "Profile %s (%s) references unknown species profile '%s'; inheritance fallbacks will be skipped.",
                display_name,
                profile_id,
                species_id,
            )
            self._missing_species_logged.add(key)
            self._create_species_issue(profile_id, display_name, species_id)

        resolved_species = self._missing_species_issues - current_species
        for profile_id, species_id in sorted(resolved_species):
            self._clear_species_issue(profile_id, species_id)
            self._missing_species_logged.discard((profile_id, species_id))

        current_parents: set[tuple[str, str]] = set()
        for profile_id, parents in sorted(report.missing_parents.items()):
            for parent_id in sorted(parents):
                key = (profile_id, parent_id)
                current_parents.add(key)
                if key in self._missing_parents_logged:
                    continue
                profile = self._profiles.get(profile_id)
                display_name = profile.display_name if profile else profile_id
                _LOGGER.warning(
                    (
                        "Profile %s (%s) references unknown parent profile '%s'; "
                        "remove or correct the parent link to restore inheritance."
                    ),
                    display_name,
                    profile_id,
                    parent_id,
                )
                self._missing_parents_logged.add(key)
                self._create_parent_issue(profile_id, display_name, parent_id)

        resolved_parents = self._missing_parent_issues - current_parents
        for profile_id, parent_id in sorted(resolved_parents):
            self._clear_parent_issue(profile_id, parent_id)
            self._missing_parents_logged.discard((profile_id, parent_id))

        self._lineage_missing_species = current_species
        self._lineage_missing_parents = current_parents
        self._lineage_notification_dirty = True
        self.hass.async_create_task(self._async_maybe_refresh_lineage_notification())

    def _validate_profile(self, profile: BioProfile) -> list[str]:
        schema = _load_profile_schema()
        if not schema:
            self._validation_issues.pop(profile.profile_id, None)
            self._clear_validation_issue(profile.profile_id)
            return []
        try:
            payload = profile.to_json()
        except Exception as err:  # pragma: no cover - defensive logging
            _LOGGER.warning("Unable to serialise profile %s for validation: %s", profile.profile_id, err)
            issues = [f"Unable to validate profile payload: {err}"]
        else:
            issues = validate_profile_dict(payload, schema)
            for issue in issues:
                _LOGGER.warning("Profile %s schema validation issue: %s", profile.profile_id, issue)

            resolved_section = profile.resolved_section()
            threshold_issues = evaluate_threshold_bounds(resolved_section.thresholds)
            for violation in threshold_issues:
                message = violation.message()
                _LOGGER.warning(
                    "Profile %s threshold validation issue: %s",
                    profile.profile_id,
                    message,
                )
                issues.append(message)

        issues_list = [str(issue) for issue in issues]
        if issues_list:
            self._validation_issues[profile.profile_id] = issues_list
        else:
            self._validation_issues.pop(profile.profile_id, None)
        self._sync_validation_issue(profile, issues_list)
        self._validation_dirty = True
        return issues_list

    def _ensure_valid_event(
        self,
        *,
        context: str,
        payload: Mapping[str, Any],
        validator: Callable[[Mapping[str, Any]], list[str]],
    ) -> None:
        """Raise ``ValueError`` if ``payload`` fails schema validation."""

        issues = validator(payload)
        if not issues:
            return
        summary = "; ".join(issues[:3])
        if len(issues) > 3:
            summary += f" (+{len(issues) - 3} more)"
        raise ValueError(f"{context} validation failed: {summary}")

    async def _async_persist_history(
        self,
        profile_id: str,
        event_type: str,
        payload: Mapping[str, Any],
    ) -> None:
        exporter = getattr(self, "_history_exporter", None)
        if exporter is None:
            return
        try:
            await exporter.async_append(profile_id, event_type, payload)
        except Exception as err:  # pragma: no cover - best effort persistence
            _LOGGER.debug(
                "Unable to persist %s history for %s: %s",
                event_type,
                profile_id,
                err,
            )

    async def async_history_index(self) -> dict[str, dict[str, Any]]:
        exporter = getattr(self, "_history_exporter", None)
        if exporter is None:
            return {}
        records = await exporter.async_index()
        return {key: value.to_json() for key, value in records.items()}

    async def _async_maybe_refresh_validation_notification(self) -> None:
        if not self._validation_dirty:
            return
        self._validation_dirty = False
        await self._async_refresh_validation_notification()

    async def _async_refresh_validation_notification(self) -> None:
        if not self._validation_issues:
            await self._async_dismiss_notification(NOTIFICATION_PROFILE_VALIDATION)
            self._validation_digest = None
            return

        digest: tuple[tuple[str, str], ...] = tuple(
            sorted((pid, issue) for pid, issues in self._validation_issues.items() for issue in issues)
        )
        if self._validation_digest == digest:
            return

        self._validation_digest = digest
        lines = ["The following profiles failed schema validation:", ""]
        for pid, issues in sorted(self._validation_issues.items()):
            title = self._profiles.get(pid).display_name if pid in self._profiles else pid
            lines.append(f"- {title} ({pid})")
            for idx, issue in enumerate(issues):
                if idx >= 3:
                    remaining = len(issues) - idx
                    lines.append(f"  • (+{remaining} additional issues)")
                    break
                lines.append(f"  • {issue}")
            lines.append("")
        lines.append("Fix the profile JSON or remove invalid overrides, then reload the integration.")
        message = "\n".join(lines)
        await self._async_create_notification(
            message,
            notification_id=NOTIFICATION_PROFILE_VALIDATION,
            title="Horticulture Assistant profile validation error",
        )

    async def _async_maybe_refresh_lineage_notification(self) -> None:
        if not self._lineage_notification_dirty:
            return
        self._lineage_notification_dirty = False
        await self._async_refresh_lineage_notification()

    async def _async_refresh_lineage_notification(self) -> None:
        missing_species = sorted(self._lineage_missing_species)
        missing_parents = sorted(self._lineage_missing_parents)

        if not missing_species and not missing_parents:
            if self._lineage_notification_digest is not None:
                await self._async_dismiss_notification(NOTIFICATION_PROFILE_LINEAGE)
                self._lineage_notification_digest = None
            return

        digest: tuple[tuple[str, str, str], ...] = tuple(
            [("species", pid, sid) for pid, sid in missing_species]
            + [("parent", pid, parent_id) for pid, parent_id in missing_parents]
        )
        if digest == self._lineage_notification_digest:
            return

        self._lineage_notification_digest = digest

        lines = [
            (
                "Some profiles reference missing species or parent profiles, so "
                "inheritance fallbacks are currently disabled."
            ),
            "",
        ]

        if missing_species:
            lines.append("Missing species references:")
            for profile_id, species_id in missing_species:
                profile = self._profiles.get(profile_id)
                display_name = profile.display_name if profile else profile_id
                lines.append(f"- {display_name} ({profile_id}) → {species_id}")
            lines.append("")

        if missing_parents:
            lines.append("Missing parent references:")
            for profile_id, parent_id in missing_parents:
                profile = self._profiles.get(profile_id)
                display_name = profile.display_name if profile else profile_id
                lines.append(f"- {display_name} ({profile_id}) → {parent_id}")
            lines.append("")

        lines.append(
            "Add the referenced profiles or update the IDs, then reload Horticulture Assistant to restore inheritance."
        )

        message = "\n".join(lines)
        await self._async_create_notification(
            message,
            notification_id=NOTIFICATION_PROFILE_LINEAGE,
            title="Horticulture Assistant lineage warning",
        )

    async def _async_create_notification(self, message: str, *, notification_id: str, title: str) -> None:
        try:
            await self.hass.services.async_call(
                "persistent_notification",
                "create",
                {
                    "title": title,
                    "message": message,
                    "notification_id": notification_id,
                },
                blocking=True,
            )
        except KeyError:  # pragma: no cover - persistent notification unavailable in tests
            return

    async def _async_dismiss_notification(self, notification_id: str) -> None:
        try:
            await self.hass.services.async_call(
                "persistent_notification",
                "dismiss",
                {"notification_id": notification_id},
                blocking=True,
            )
        except KeyError:  # pragma: no cover - persistent notification unavailable in tests
            return

    # ------------------------------------------------------------------
    # Cloud sync helpers
    # ------------------------------------------------------------------
    def attach_cloud_publisher(self, publisher: CloudSyncPublisher | None) -> None:
        """Attach a cloud publisher so mutations are queued for sync."""

        self._cloud_publisher = publisher
        self.publish_full_snapshot()

    def publish_full_snapshot(self) -> None:
        """Publish all known profiles and histories to the cloud outbox."""

        publisher = self._cloud_publisher
        if publisher is None:
            return
        if not publisher.ready:
            self._cloud_pending_snapshot = True
            return
        self._cloud_pending_snapshot = False
        self._publish_snapshot(publisher)

    def _publish_snapshot(self, publisher: CloudSyncPublisher) -> None:
        for profile in self._profiles.values():
            self._safe_publish(lambda prof=profile: publisher.publish_profile(prof, initial=True))
            self._publish_stats_with(publisher, profile, initial=True)
            for event in profile.run_history:
                self._safe_publish(lambda ev=event: publisher.publish_run(ev, initial=True))
            for event in profile.harvest_history:
                self._safe_publish(lambda ev=event: publisher.publish_harvest(ev, initial=True))
            for event in profile.nutrient_history:
                self._safe_publish(lambda ev=event: publisher.publish_nutrient(ev, initial=True))
            for event in profile.event_history:
                self._safe_publish(lambda ev=event: publisher.publish_cultivation(ev, initial=True))

    def _safe_publish(self, callback: Callable[[], Any]) -> None:
        try:
            callback()
        except Exception as err:  # pragma: no cover - defensive logging
            _LOGGER.debug("Cloud publish skipped due to error: %s", err, exc_info=True)

    def _cloud_publish_profile(self, profile: BioProfile) -> None:
        publisher = self._cloud_publisher
        if publisher is None:
            return
        if self._cloud_pending_snapshot:
            self.publish_full_snapshot()
            publisher = self._cloud_publisher
        if publisher is None:
            self._cloud_pending_snapshot = True
            return
        ready = publisher.ready
        self._safe_publish(lambda: publisher.publish_profile(profile))
        self._publish_stats_with(publisher, profile)
        self._cloud_pending_snapshot = not ready

    def _cloud_publish_deleted(self, profile_id: str) -> None:
        publisher = self._cloud_publisher
        if publisher is None:
            return
        if self._cloud_pending_snapshot:
            self.publish_full_snapshot()
            publisher = self._cloud_publisher
        if publisher is None:
            self._cloud_pending_snapshot = True
            return
        ready = publisher.ready
        self._safe_publish(lambda: publisher.publish_profile_deleted(profile_id))
        if ready:
            self._cloud_pending_snapshot = False
        else:
            self._cloud_pending_snapshot = True

    def _cloud_publish_run(self, event: RunEvent) -> None:
        publisher = self._cloud_publisher
        if publisher is None:
            return
        if self._cloud_pending_snapshot:
            self.publish_full_snapshot()
            publisher = self._cloud_publisher
        if publisher is None:
            self._cloud_pending_snapshot = True
            return
        ready = publisher.ready
        self._safe_publish(lambda: publisher.publish_run(event))
        if ready:
            self._cloud_pending_snapshot = False
        else:
            self._cloud_pending_snapshot = True

    def _cloud_publish_harvest(self, event: HarvestEvent) -> None:
        publisher = self._cloud_publisher
        if publisher is None:
            return
        if self._cloud_pending_snapshot:
            self.publish_full_snapshot()
            publisher = self._cloud_publisher
        if publisher is None:
            self._cloud_pending_snapshot = True
            return
        ready = publisher.ready
        self._safe_publish(lambda: publisher.publish_harvest(event))
        if ready:
            self._cloud_pending_snapshot = False
        else:
            self._cloud_pending_snapshot = True

    def _cloud_publish_nutrient(self, event: NutrientApplication) -> None:
        publisher = self._cloud_publisher
        if publisher is None:
            return
        if self._cloud_pending_snapshot:
            self.publish_full_snapshot()
            publisher = self._cloud_publisher
        if publisher is None:
            self._cloud_pending_snapshot = True
            return
        ready = publisher.ready
        self._safe_publish(lambda: publisher.publish_nutrient(event))
        if ready:
            self._cloud_pending_snapshot = False
        else:
            self._cloud_pending_snapshot = True

    def _cloud_publish_cultivation(self, event: CultivationEvent) -> None:
        publisher = self._cloud_publisher
        if publisher is None:
            return
        if self._cloud_pending_snapshot:
            self.publish_full_snapshot()
            publisher = self._cloud_publisher
        if publisher is None:
            self._cloud_pending_snapshot = True
            return
        ready = publisher.ready
        self._safe_publish(lambda: publisher.publish_cultivation(event))
        if ready:
            self._cloud_pending_snapshot = False
        else:
            self._cloud_pending_snapshot = True

    def _async_fire_history_event(
        self,
        event_type: str,
        profile: BioProfile,
        payload: Mapping[str, Any],
        *,
        event_kind: str,
        event_subtype: str | None = None,
        run_id: str | None = None,
    ) -> None:
        """Emit a Home Assistant event describing a history update."""

        data: dict[str, Any] = {
            "profile_id": profile.profile_id,
            "profile_type": profile.profile_type,
            "display_name": profile.display_name,
            "event_kind": event_kind,
            "event": dict(payload),
        }
        if run_id:
            data["run_id"] = run_id
        if event_subtype:
            data["event_subtype"] = event_subtype
        species_id = getattr(profile, "species", None)
        if species_id:
            data["species_id"] = species_id
        parents = getattr(profile, "parents", None)
        if parents:
            data["parents"] = list(parents)
        bus = getattr(self.hass, "bus", None)
        fire = getattr(bus, "async_fire", None)
        if callable(fire):
            fire(event_type, data)

    def _publish_stats_with(
        self,
        publisher: CloudSyncPublisher,
        profile: BioProfile,
        *,
        initial: bool = False,
    ) -> None:
        for snapshot in profile.computed_stats:
            if not isinstance(snapshot, ComputedStatSnapshot):
                continue
            self._safe_publish(lambda snap=snapshot: publisher.publish_stat_snapshot(profile, snap, initial=initial))

    # ---------------------------------------------------------------------
    # Initialization and access helpers
    # ---------------------------------------------------------------------
    async def async_load(self) -> None:
        """Load profiles from storage and config entry options."""

        data = await self._store.async_load() or {}
        if not data:
            cache = self.hass.data.get(PROFILE_STORE_CACHE_KEY)
            if isinstance(cache, Mapping):
                data = {k: deepcopy(v) for k, v in cache.items() if isinstance(k, str)}

        # Older versions stored profiles as a list; convert to the new mapping
        # structure keyed by the legacy ``plant_id`` identifier.
        if isinstance(data, list):  # pragma: no cover - legacy format
            data = {"profiles": {p["plant_id"]: p for p in data if isinstance(p, Mapping) and p.get("plant_id")}}

        stored_profiles: Mapping[str, Any] = {}
        if isinstance(data, Mapping):
            candidate = data.get("profiles") if "profiles" in data else None
            if isinstance(candidate, Mapping):
                stored_profiles = candidate
            else:
                # Older helpers stored the mapping directly without a wrapper key.
                legacy_profiles: dict[str, Any] = {}
                for key, value in data.items():
                    if isinstance(key, str) and isinstance(value, Mapping):
                        legacy_profiles[key] = value
                    else:
                        legacy_profiles = {}
                        break
                stored_profiles = legacy_profiles

        profiles: dict[str, BioProfile] = {}

        stored_objects: dict[str, BioProfile] = {}
        for pid, payload in stored_profiles.items():
            if not isinstance(payload, Mapping):
                _LOGGER.warning(
                    "Skipping invalid stored profile %s: expected mapping but received %s",
                    pid,
                    type(payload).__name__,
                )
                continue

            try:
                profile = BioProfile.from_json(dict(payload))
            except Exception:
                normalised = dict(payload)
                try:
                    ensure_sections(
                        normalised,
                        plant_id=pid,
                        display_name=normalised.get("name") or pid,
                    )
                except Exception as normalise_err:
                    _LOGGER.warning(
                        "Skipping invalid stored profile %s: %s",
                        pid,
                        normalise_err,
                    )
                    continue
                try:
                    profile = BioProfile.from_json(normalised)
                except Exception as final_err:
                    _LOGGER.warning(
                        "Skipping invalid stored profile %s: %s",
                        pid,
                        final_err,
                    )
                    continue

            stored_objects[pid] = profile
            profiles[pid] = profile
            self._validate_profile(profile)

        options_profiles = self.entry.options.get(CONF_PROFILES, {}) or {}
        if not isinstance(options_profiles, Mapping):
            _LOGGER.warning(
                "Ignoring invalid config entry profiles payload: expected mapping but received %s",
                type(options_profiles).__name__,
            )
            options_profiles = {}

        for pid, payload in options_profiles.items():
            display_name = payload.get("name") or pid
            try:
                profile = options_profile_to_dataclass(
                    pid,
                    payload,
                    display_name=display_name,
                )
            except Exception:
                copy = dict(payload)
                ensure_sections(copy, plant_id=pid, display_name=display_name)
                profile = BioProfile.from_json(copy)

            stored_profile = stored_objects.get(pid)
            if stored_profile is not None:
                profile = self._merge_profile_data(stored_profile, profile)
            self._validate_profile(profile)
            profiles[pid] = profile

        for profile in profiles.values():
            profile.general.setdefault(CONF_PROFILE_SCOPE, PROFILE_SCOPE_DEFAULT)

        self._profiles = profiles
        self._relink_profiles()
        recompute_statistics(self._profiles.values())
        await self._async_maybe_refresh_validation_notification()

    async def async_save(self) -> None:
        self._relink_profiles()
        recompute_statistics(self._profiles.values())
        payload = {pid: prof.to_json() for pid, prof in self._profiles.items()}
        cache = self.hass.data.setdefault(PROFILE_STORE_CACHE_KEY, {})
        cache.clear()
        cache.update({pid: deepcopy(data) for pid, data in payload.items()})
        await self._store.async_save({"profiles": payload})

    # Backwards compatibility for previous method name
    async_initialize = async_load

    def list_profiles(self) -> list[BioProfile]:
        """Return all known profiles."""

        return list(self._profiles.values())

    def iter_profiles(self) -> list[BioProfile]:
        return self.list_profiles()

    def get_profile(self, plant_id: str) -> BioProfile | None:
        """Return a specific profile by id."""

        return self._profiles.get(plant_id)

    # Backwards compatibility for existing tests
    get = get_profile

    # ---------------------------------------------------------------------
    # Mutation helpers
    # ---------------------------------------------------------------------
    async def async_replace_sensor(self, profile_id: str, measurement: str, entity_id: str) -> None:
        """Update a profile's bound sensor entity.

        This mirrors the behaviour of the ``replace_sensor`` service but
        allows tests and other components to call the logic directly.
        """

        profiles = dict(self.entry.options.get(CONF_PROFILES, {}))
        profile = profiles.get(profile_id)
        if profile is None:
            raise ValueError(f"unknown profile {profile_id}")
        entity_text = str(entity_id).strip() if entity_id is not None else ""
        if not entity_text:
            raise ValueError("entity_id must be a non-empty string")
        prof_payload = dict(profile)
        ensure_sections(
            prof_payload,
            plant_id=profile_id,
            display_name=prof_payload.get("name") or profile_id,
        )
        general = dict(prof_payload.get("general", {})) if isinstance(prof_payload.get("general"), Mapping) else {}
        sensors = dict(general.get("sensors", {}))
        sensors[measurement] = entity_text
        general["sensors"] = sensors
        sync_general_section(prof_payload, general)
        prof_payload["sensors"] = dict(sensors)
        profiles[profile_id] = prof_payload
        new_opts = dict(self.entry.options)
        new_opts[CONF_PROFILES] = profiles
        # Update config entry and keep local copy in sync for tests.
        self.hass.config_entries.async_update_entry(self.entry, options=new_opts)
        self.entry.options = new_opts

        # Mirror changes into in-memory structure if profile exists.
        if prof_obj := self._profiles.get(profile_id):
            general_map = dict(prof_obj.general)
            current = general_map.get("sensors")
            merged = dict(current) if isinstance(current, Mapping) else {}
            merged[measurement] = entity_text
            general_map["sensors"] = merged
            prof_obj.general = general_map
            prof_obj.refresh_sections()
            self._validate_profile(prof_obj)
        await self.async_save()
        if prof_obj := self._profiles.get(profile_id):
            self._cloud_publish_profile(prof_obj)
        await self._async_maybe_refresh_validation_notification()

    async def async_refresh_species(self, profile_id: str) -> None:
        """Placeholder for species refresh logic.

        The real integration refreshes thresholds from OpenPlantbook or other
        sources.  For the lightweight registry we simply mark the profile as
        refreshed, leaving the heavy lifting to the coordinators.
        """

        prof = self._profiles.get(profile_id)
        if not prof:
            raise ValueError(f"unknown profile {profile_id}")
        prof.last_resolved = "1970-01-01T00:00:00Z"
        prof.refresh_sections()
        await self.async_save()
        self._cloud_publish_profile(prof)

    async def async_export(self, path: str | Path) -> Path:
        """Export all profiles to a JSON file and return the path."""

        p = Path(path)
        if not p.is_absolute():
            p = Path(self.hass.config.path(str(p)))  # type: ignore[attr-defined]
        p.parent.mkdir(parents=True, exist_ok=True)
        data = [p_.to_json() for p_ in self._profiles.values()]
        with p.open("w", encoding="utf-8") as fp:
            json.dump(data, fp, indent=2, ensure_ascii=False)
            fp.write("\n")
        return p

    async def async_add_profile(
        self,
        name: str,
        base_id: str | None = None,
        scope: str | None = None,
    ) -> str:
        profiles = dict(self.entry.options.get(CONF_PROFILES, {}))
        base = slugify(name) or "profile"
        candidate = base
        idx = 1
        while candidate in profiles or candidate in self._profiles:
            candidate = f"{base}_{idx}"
            idx += 1

        new_profile: dict[str, Any] = {"name": name}
        base_profile_obj: BioProfile | None = None
        if base_id:
            source = profiles.get(base_id)
            if source is None:
                base_profile_obj = self._profiles.get(base_id)
                if base_profile_obj is None:
                    raise ValueError(f"unknown profile {base_id}")
                source = base_profile_obj.to_json()
            elif isinstance(self._profiles.get(base_id), BioProfile):
                base_profile_obj = self._profiles.get(base_id)

            if not isinstance(source, Mapping):
                raise ValueError(f"invalid profile payload for {base_id}")

            source_map = dict(source)
            new_profile = deepcopy(source_map)
            new_profile["name"] = name
            if scope is None:
                candidate_scope = None
                general = source_map.get("general")
                if isinstance(general, Mapping):
                    candidate_scope = general.get(CONF_PROFILE_SCOPE)
                if candidate_scope is None:
                    candidate_scope = source_map.get(CONF_PROFILE_SCOPE) or source_map.get("scope")
                if candidate_scope is None and isinstance(base_profile_obj, BioProfile):
                    candidate_scope = base_profile_obj.general.get(CONF_PROFILE_SCOPE)
                scope = candidate_scope

        resolved_scope = scope or PROFILE_SCOPE_DEFAULT
        if resolved_scope not in PROFILE_SCOPE_CHOICES:
            raise ValueError(f"invalid scope {resolved_scope}")

        ensure_sections(
            new_profile,
            plant_id=candidate,
            display_name=name,
        )
        general = dict(new_profile.get("general", {})) if isinstance(new_profile.get("general"), Mapping) else {}
        sensors_map: dict[str, str | list[str]] = {}
        raw_sensors = new_profile.get("sensors")
        if isinstance(raw_sensors, Mapping):
            for key, value in raw_sensors.items():
                cleaned = _normalise_sensor_value(value)
                if cleaned is None:
                    continue
                sensors_map[str(key)] = cleaned
        general_sensors = general.get("sensors") if isinstance(general.get("sensors"), Mapping) else {}
        for key, value in general_sensors.items():
            cleaned = _normalise_sensor_value(value)
            if cleaned is None:
                continue
            sensors_map[str(key)] = cleaned
        general[CONF_PROFILE_SCOPE] = resolved_scope
        if sensors_map:
            general["sensors"] = {
                key: list(value) if isinstance(value, list) else value for key, value in sensors_map.items()
            }
        sync_general_section(new_profile, general)
        if sensors_map:
            new_profile["sensors"] = {
                key: list(value) if isinstance(value, list) else value for key, value in sensors_map.items()
            }
        else:
            new_profile.pop("sensors", None)
        new_profile.pop("scope", None)
        new_profile[CONF_PROFILE_SCOPE] = resolved_scope
        new_profile["profile_id"] = candidate
        new_profile["plant_id"] = candidate
        profiles[candidate] = new_profile
        new_opts = dict(self.entry.options)
        new_opts[CONF_PROFILES] = profiles
        self.hass.config_entries.async_update_entry(self.entry, options=new_opts)
        self.entry.options = new_opts

        prof_obj = options_profile_to_dataclass(
            candidate,
            new_profile,
            display_name=name,
        )
        prof_obj.refresh_sections()
        self._validate_profile(prof_obj)
        self._profiles[candidate] = prof_obj
        self._relink_profiles()
        await self.async_save()
        self._cloud_publish_profile(prof_obj)
        await self._async_maybe_refresh_validation_notification()
        return candidate

    async def async_duplicate_profile(self, source_id: str, new_name: str) -> str:
        """Duplicate ``source_id`` into a new profile with ``new_name``."""

        return await self.async_add_profile(new_name, base_id=source_id)

    async def async_delete_profile(self, profile_id: str) -> None:
        """Remove ``profile_id`` from the registry and storage."""

        profiles = dict(self.entry.options.get(CONF_PROFILES, {}))
        if profile_id not in profiles:
            raise ValueError(f"unknown profile {profile_id}")
        profiles.pop(profile_id)
        new_opts = dict(self.entry.options)
        new_opts[CONF_PROFILES] = profiles
        self.hass.config_entries.async_update_entry(self.entry, options=new_opts)
        self.entry.options = new_opts
        self._profiles.pop(profile_id, None)
        self._clear_validation_issue(profile_id)
        self._relink_profiles()
        if self._validation_issues.pop(profile_id, None) is not None:
            self._validation_dirty = True
        await self.async_save()
        self._cloud_publish_deleted(profile_id)
        await self._async_maybe_refresh_validation_notification()

    async def async_link_sensors(self, profile_id: str, sensors: dict[str, str]) -> None:
        """Link multiple sensor entities to ``profile_id``."""

        profiles = dict(self.entry.options.get(CONF_PROFILES, {}))
        profile = profiles.get(profile_id)
        if profile is None:
            raise ValueError(f"unknown profile {profile_id}")
        cleaned: dict[str, str] = {}
        for key, value in sensors.items():
            if not isinstance(key, str):
                key = str(key)
            if not isinstance(value, str):
                continue
            entity_id = value.strip()
            if not entity_id:
                continue
            cleaned[key] = entity_id

        validation = validate_sensor_links(self.hass, cleaned)
        if validation.errors:
            message = collate_issue_messages(validation.errors)
            raise ValueError(f"sensor validation failed: {message}")
        if validation.warnings:
            _LOGGER.warning(
                "Profile %s sensor validation warnings:\n%s",
                profile_id,
                collate_issue_messages(validation.warnings),
            )
        prof_payload = dict(profile)
        ensure_sections(
            prof_payload,
            plant_id=profile_id,
            display_name=prof_payload.get("name") or profile_id,
        )
        general = dict(prof_payload.get("general", {})) if isinstance(prof_payload.get("general"), Mapping) else {}
        merged = dict(general.get("sensors", {}))
        for key, value in cleaned.items():
            merged[str(key)] = value
        general["sensors"] = merged
        sync_general_section(prof_payload, general)
        prof_payload["sensors"] = dict(merged)
        profiles[profile_id] = prof_payload
        new_opts = dict(self.entry.options)
        new_opts[CONF_PROFILES] = profiles
        self.hass.config_entries.async_update_entry(self.entry, options=new_opts)
        self.entry.options = new_opts
        if prof_obj := self._profiles.get(profile_id):
            general_map = dict(prof_obj.general)
            general_map["sensors"] = dict(merged)
            prof_obj.general = general_map
            prof_obj.refresh_sections()
            self._validate_profile(prof_obj)
        await self.async_save()
        if prof_obj := self._profiles.get(profile_id):
            self._cloud_publish_profile(prof_obj)
        await self._async_maybe_refresh_validation_notification()

    async def async_set_profile_sensors(self, profile_id: str, sensors: Mapping[str, str] | None) -> None:
        """Replace the sensor mapping for ``profile_id``."""

        profiles = dict(self.entry.options.get(CONF_PROFILES, {}))
        profile = profiles.get(profile_id)
        if profile is None:
            raise ValueError(f"unknown profile {profile_id}")

        cleaned: dict[str, str] = {}
        if sensors:
            for key, value in sensors.items():
                if not isinstance(key, str):
                    key = str(key)
                if not isinstance(value, str):
                    continue
                entity_id = value.strip()
                if not entity_id:
                    continue
                cleaned[key] = entity_id

        if cleaned:
            validation = validate_sensor_links(self.hass, cleaned)
            if validation.errors:
                message = collate_issue_messages(validation.errors)
                raise ValueError(message)
            if validation.warnings:
                _LOGGER.warning(
                    "Profile %s sensor validation warnings:\n%s",
                    profile_id,
                    collate_issue_messages(validation.warnings),
                )

        prof_payload = dict(profile)
        ensure_sections(
            prof_payload,
            plant_id=profile_id,
            display_name=prof_payload.get("name") or profile_id,
        )
        general = dict(prof_payload.get("general", {})) if isinstance(prof_payload.get("general"), Mapping) else {}
        if cleaned:
            general["sensors"] = dict(cleaned)
            prof_payload["sensors"] = dict(cleaned)
        else:
            general.pop("sensors", None)
            prof_payload.pop("sensors", None)
        sync_general_section(prof_payload, general)
        profiles[profile_id] = prof_payload
        new_opts = dict(self.entry.options)
        new_opts[CONF_PROFILES] = profiles
        self.hass.config_entries.async_update_entry(self.entry, options=new_opts)
        self.entry.options = new_opts

        prof_obj = self._profiles.get(profile_id)
        if prof_obj is not None:
            general_map = dict(prof_obj.general)
            if cleaned:
                general_map["sensors"] = dict(cleaned)
            else:
                general_map.pop("sensors", None)
            prof_obj.general = general_map
            prof_obj.refresh_sections()
            self._validate_profile(prof_obj)
        await self.async_save()
        if prof_obj is not None:
            self._cloud_publish_profile(prof_obj)
        await self._async_maybe_refresh_validation_notification()

    async def async_update_profile_thresholds(
        self,
        profile_id: str,
        thresholds: Mapping[str, Any] | None,
        *,
        allowed_keys: Iterable[str] | None = None,
        removed_keys: Iterable[str] | None = None,
        default_source: str = "manual",
    ) -> None:
        """Update threshold targets for ``profile_id`` while syncing metadata."""

        profiles = dict(self.entry.options.get(CONF_PROFILES, {}))
        profile = profiles.get(profile_id)
        if profile is None:
            raise ValueError(f"unknown profile {profile_id}")

        prof_payload = dict(profile)
        ensure_sections(
            prof_payload,
            plant_id=profile_id,
            display_name=prof_payload.get("name") or profile_id,
        )

        threshold_map = (
            dict(prof_payload.get("thresholds", {})) if isinstance(prof_payload.get("thresholds"), Mapping) else {}
        )

        cleaned: dict[str, float] = {}
        if thresholds:
            for key, raw in thresholds.items():
                if raw is None:
                    continue
                try:
                    value = float(raw)
                except (TypeError, ValueError) as err:
                    raise ValueError(f"invalid threshold {key}") from err
                if not isfinite(value):
                    raise ValueError(f"non-finite threshold value for {key}")
                cleaned[str(key)] = value

        removals = {str(key) for key in removed_keys} if removed_keys else set()

        if allowed_keys is not None:
            allowed_set: set[str] = {str(key) for key in allowed_keys}
            target_keys = allowed_set | removals
        else:
            allowed_set = set(cleaned.keys())
            target_keys = allowed_set | removals

        updated_map = dict(threshold_map)
        for key in target_keys:
            if key in cleaned:
                updated_map[key] = cleaned[key]
            elif key in removals:
                updated_map.pop(key, None)

        violations = evaluate_threshold_bounds(updated_map)
        if violations:
            summary = [issue.message() for issue in violations]
            raise ValueError("\n".join(summary))

        prof_payload["thresholds"] = updated_map
        sync_thresholds(
            prof_payload,
            default_source=default_source,
            touched_keys=target_keys or None,
            prune=True,
        )

        profiles[profile_id] = prof_payload
        new_opts = dict(self.entry.options)
        new_opts[CONF_PROFILES] = profiles
        self.hass.config_entries.async_update_entry(self.entry, options=new_opts)
        self.entry.options = new_opts

        prof_obj = self._profiles.get(profile_id)
        if prof_obj is not None:
            resolved_payload = (
                prof_payload.get("resolved_targets")
                if isinstance(prof_payload.get("resolved_targets"), Mapping)
                else {}
            )
            resolved: dict[str, ResolvedTarget] = {}
            if isinstance(resolved_payload, Mapping):
                for key, value in resolved_payload.items():
                    if isinstance(value, ResolvedTarget):
                        resolved[str(key)] = value
                    elif isinstance(value, Mapping):
                        resolved[str(key)] = ResolvedTarget.from_json(dict(value))
            prof_obj.resolved_targets = resolved
            prof_obj.refresh_sections()
            self._validate_profile(prof_obj)

        await self.async_save()
        if prof_obj is not None:
            self._cloud_publish_profile(prof_obj)
        await self._async_maybe_refresh_validation_notification()

    async def async_update_profile_general(
        self,
        profile_id: str,
        *,
        name: str | None = None,
        plant_type: str | None = None,
        scope: str | None = None,
        species_display: str | None = None,
    ) -> None:
        """Update high level metadata for ``profile_id``."""

        profiles = dict(self.entry.options.get(CONF_PROFILES, {}))
        profile = profiles.get(profile_id)
        if profile is None:
            raise ValueError(f"unknown profile {profile_id}")

        prof_payload = dict(profile)
        ensure_sections(
            prof_payload,
            plant_id=profile_id,
            display_name=prof_payload.get("name") or profile_id,
        )
        general = dict(prof_payload.get("general", {})) if isinstance(prof_payload.get("general"), Mapping) else {}

        display_name = name or prof_payload.get("name") or profile_id
        prof_payload["name"] = display_name
        prof_payload["display_name"] = display_name

        if plant_type:
            general["plant_type"] = plant_type
        else:
            general.pop("plant_type", None)

        resolved_scope = scope or general.get(CONF_PROFILE_SCOPE) or PROFILE_SCOPE_DEFAULT
        if resolved_scope not in PROFILE_SCOPE_CHOICES:
            raise ValueError(f"invalid scope {resolved_scope}")
        general[CONF_PROFILE_SCOPE] = resolved_scope

        if species_display:
            prof_payload["species_display"] = species_display
        else:
            prof_payload.pop("species_display", None)

        sync_general_section(prof_payload, general)
        profiles[profile_id] = prof_payload
        new_opts = dict(self.entry.options)
        new_opts[CONF_PROFILES] = profiles
        self.hass.config_entries.async_update_entry(self.entry, options=new_opts)
        self.entry.options = new_opts

        prof_obj = self._profiles.get(profile_id)
        if prof_obj is not None:
            prof_obj.display_name = display_name
            general_map = dict(prof_obj.general)
            if plant_type:
                general_map["plant_type"] = plant_type
            else:
                general_map.pop("plant_type", None)
            general_map[CONF_PROFILE_SCOPE] = resolved_scope
            prof_obj.general = general_map
            prof_obj.refresh_sections()
            self._validate_profile(prof_obj)
        await self.async_save()
        if prof_obj is not None:
            self._cloud_publish_profile(prof_obj)
        await self._async_maybe_refresh_validation_notification()

    async def async_record_run_event(
        self,
        profile_id: str,
        payload: Mapping[str, Any] | RunEvent,
    ) -> RunEvent:
        """Append a cultivation run event for ``profile_id``.

        Parameters
        ----------
        profile_id: str
            Identifier of the cultivar or species profile.
        payload: Mapping[str, Any] | RunEvent
            Raw event data or an already-instantiated :class:`RunEvent`.

        Returns
        -------
        RunEvent
            The normalised event that was stored.
        """

        prof = self._profiles.get(profile_id)
        if prof is None:
            raise ValueError(f"unknown profile {profile_id}")

        if isinstance(payload, RunEvent):
            event = payload
            if not event.profile_id:
                event.profile_id = profile_id
            self._ensure_valid_event(
                context="run event",
                payload=event.to_json(),
                validator=validate_run_event_dict,
            )
        else:
            raw_payload = dict(payload)
            raw_payload.setdefault("profile_id", profile_id)
            self._ensure_valid_event(
                context="run event",
                payload=raw_payload,
                validator=validate_run_event_dict,
            )
            event = RunEvent.from_json(raw_payload)
        prof.add_run_event(event)
        prof.updated_at = datetime.now(tz=UTC).isoformat()
        prof.refresh_sections()
        await self.async_save()
        stored = prof.run_history[-1]
        stored_payload = stored.to_json()
        self._cloud_publish_profile(prof)
        self._cloud_publish_run(stored)
        self._async_fire_history_event(
            EVENT_PROFILE_RUN_RECORDED,
            prof,
            stored_payload,
            event_kind="run",
            run_id=stored.run_id,
        )
        await self._async_persist_history(profile_id, "run", stored_payload)
        return stored

    async def async_record_harvest_event(
        self,
        profile_id: str,
        payload: Mapping[str, Any] | HarvestEvent,
    ) -> HarvestEvent:
        """Append a harvest event and recompute statistics for ``profile_id``.

        Parameters
        ----------
        profile_id: str
            Identifier of the cultivar being harvested.
        payload: Mapping[str, Any] | HarvestEvent
            Raw event data or an already-instantiated :class:`HarvestEvent`.

        Returns
        -------
        HarvestEvent
            The normalised event that was stored.
        """

        prof = self._profiles.get(profile_id)
        if prof is None:
            raise ValueError(f"unknown profile {profile_id}")

        if isinstance(payload, HarvestEvent):
            event = payload
            if not event.profile_id:
                event.profile_id = profile_id
            self._ensure_valid_event(
                context="harvest event",
                payload=event.to_json(),
                validator=validate_harvest_event_dict,
            )
        else:
            raw_payload = dict(payload)
            raw_payload.setdefault("profile_id", profile_id)
            self._ensure_valid_event(
                context="harvest event",
                payload=raw_payload,
                validator=validate_harvest_event_dict,
            )
            event = HarvestEvent.from_json(raw_payload)
        prof.add_harvest_event(event)
        prof.updated_at = datetime.now(tz=UTC).isoformat()
        prof.refresh_sections()
        await self.async_save()
        stored = prof.harvest_history[-1]
        stored_payload = stored.to_json()
        self._cloud_publish_profile(prof)
        self._cloud_publish_harvest(stored)
        self._async_fire_history_event(
            EVENT_PROFILE_HARVEST_RECORDED,
            prof,
            stored_payload,
            event_kind="harvest",
            run_id=stored.run_id,
        )
        await self._async_persist_history(profile_id, "harvest", stored_payload)
        return stored

    async def async_record_nutrient_event(
        self,
        profile_id: str,
        payload: Mapping[str, Any] | NutrientApplication,
    ) -> NutrientApplication:
        """Append a nutrient application event for ``profile_id``."""

        prof = self._profiles.get(profile_id)
        if prof is None:
            raise ValueError(f"unknown profile {profile_id}")

        if isinstance(payload, NutrientApplication):
            event = payload
            if not event.profile_id:
                event.profile_id = profile_id
            self._ensure_valid_event(
                context="nutrient event",
                payload=event.to_json(),
                validator=validate_nutrient_event_dict,
            )
        else:
            raw_payload = dict(payload)
            raw_payload.setdefault("profile_id", profile_id)
            self._ensure_valid_event(
                context="nutrient event",
                payload=raw_payload,
                validator=validate_nutrient_event_dict,
            )
            event = NutrientApplication.from_json(raw_payload)
        prof.add_nutrient_event(event)
        prof.updated_at = datetime.now(tz=UTC).isoformat()
        prof.refresh_sections()
        await self.async_save()
        stored = prof.nutrient_history[-1]
        stored_payload = stored.to_json()
        self._cloud_publish_profile(prof)
        self._cloud_publish_nutrient(stored)
        self._async_fire_history_event(
            EVENT_PROFILE_NUTRIENT_RECORDED,
            prof,
            stored_payload,
            event_kind="nutrient",
            run_id=stored.run_id,
        )
        await self._async_persist_history(profile_id, "nutrient", stored_payload)
        return stored

    async def async_record_cultivation_event(
        self,
        profile_id: str,
        payload: Mapping[str, Any] | CultivationEvent,
    ) -> CultivationEvent:
        """Append a cultivation milestone event for ``profile_id``."""

        prof = self._profiles.get(profile_id)
        if prof is None:
            raise ValueError(f"unknown profile {profile_id}")

        if isinstance(payload, CultivationEvent):
            event = payload
            if not event.profile_id:
                event.profile_id = profile_id
            self._ensure_valid_event(
                context="cultivation event",
                payload=event.to_json(),
                validator=validate_cultivation_event_dict,
            )
        else:
            raw_payload = dict(payload)
            raw_payload.setdefault("profile_id", profile_id)
            self._ensure_valid_event(
                context="cultivation event",
                payload=raw_payload,
                validator=validate_cultivation_event_dict,
            )
            event = CultivationEvent.from_json(raw_payload)
        prof.add_cultivation_event(event)
        prof.updated_at = datetime.now(tz=UTC).isoformat()
        prof.refresh_sections()
        await self.async_save()
        stored = prof.event_history[-1]
        stored_payload = stored.to_json()
        self._cloud_publish_profile(prof)
        self._cloud_publish_cultivation(stored)
        self._async_fire_history_event(
            EVENT_PROFILE_CULTIVATION_RECORDED,
            prof,
            stored_payload,
            event_kind="cultivation",
            event_subtype=stored.event_type,
            run_id=stored.run_id,
        )
        await self._async_persist_history(profile_id, "cultivation", stored_payload)
        return stored

    async def async_import_template(self, template: str, name: str | None = None) -> str:
        """Create a profile from a bundled template.

        Templates are stored under ``data/templates/<template>.json`` and
        contain a serialised :class:`BioProfile`.  The new profile will copy
        variables and metadata from the template while generating a unique
        identifier based on ``name`` or the template's display name.
        """

        template_path = Path(__file__).parent / "data" / "templates" / f"{template}.json"
        if not template_path.exists():
            raise ValueError(f"unknown template {template}")

        text = template_path.read_text(encoding="utf-8")
        data = json.loads(text)
        prof = BioProfile.from_json(data)
        scope = (prof.general or {}).get(CONF_PROFILE_SCOPE)
        pid = await self.async_add_profile(name or prof.display_name, scope=scope)
        new_prof = self._profiles[pid]
        new_prof.species = prof.species
        new_prof.profile_type = prof.profile_type
        new_prof.parents = list(prof.parents)
        new_prof.identity = dict(prof.identity)
        new_prof.taxonomy = dict(prof.taxonomy)
        new_prof.policies = dict(prof.policies)
        new_prof.stable_knowledge = dict(prof.stable_knowledge)
        new_prof.lifecycle = dict(prof.lifecycle)
        new_prof.traits = dict(prof.traits)
        new_prof.tags = list(prof.tags)
        new_prof.curated_targets = dict(prof.curated_targets)
        new_prof.diffs_vs_parent = dict(prof.diffs_vs_parent)
        new_prof.local_overrides = dict(prof.local_overrides)
        new_prof.resolver_state = dict(prof.resolver_state)
        new_prof.resolved_targets = {k: deepcopy(v) for k, v in prof.resolved_targets.items()}
        new_prof.computed_stats = [deepcopy(stat) for stat in prof.computed_stats]
        new_prof.general.update(prof.general)
        new_prof.general.setdefault(CONF_PROFILE_SCOPE, scope or PROFILE_SCOPE_DEFAULT)
        new_prof.citations = [deepcopy(cit) for cit in prof.citations]
        new_prof.last_resolved = prof.last_resolved
        new_prof.refresh_sections()
        self._validate_profile(new_prof)
        self._relink_profiles()

        # Persist the template payload back to the config entry options so the UI
        # and other helpers immediately see the imported thresholds and
        # metadata.  ``BioProfile.to_json`` returns mutable references for the
        # ``general`` section, so work on copies before storing them.
        profiles = dict(self.entry.options.get(CONF_PROFILES, {}))
        options_payload = new_prof.to_json()
        options_payload["name"] = new_prof.display_name
        general_payload = (
            dict(options_payload.get("general", {})) if isinstance(options_payload.get("general"), Mapping) else {}
        )
        sensors_payload = (
            dict(general_payload.get("sensors", {})) if isinstance(general_payload.get("sensors"), Mapping) else {}
        )
        if sensors_payload:
            general_payload["sensors"] = sensors_payload
            options_payload["sensors"] = dict(sensors_payload)
        else:
            general_payload.pop("sensors", None)
            options_payload.pop("sensors", None)
        general_payload.setdefault(
            CONF_PROFILE_SCOPE,
            new_prof.general.get(CONF_PROFILE_SCOPE, PROFILE_SCOPE_DEFAULT),
        )
        options_payload["general"] = general_payload
        options_payload.pop("scope", None)
        options_payload[CONF_PROFILE_SCOPE] = general_payload.get(CONF_PROFILE_SCOPE)
        profiles[pid] = options_payload
        new_opts = dict(self.entry.options)
        new_opts[CONF_PROFILES] = profiles
        self.hass.config_entries.async_update_entry(self.entry, options=new_opts)
        self.entry.options = new_opts
        await self.async_save()
        self._cloud_publish_profile(new_prof)
        return pid

    async def async_export_profile(self, profile_id: str, path: str | Path) -> Path:
        """Export a single profile to ``path`` and return it."""

        from .profile.export import async_export_profile

        return await async_export_profile(self.hass, profile_id, path)

    async def async_import_profiles(self, path: str | Path) -> int:
        """Import profiles from ``path`` and reload the registry."""

        from .profile.importer import async_import_profiles

        existing_options = self.entry.options.get(CONF_PROFILES)
        existing_profiles: dict[str, Any] = {}
        if isinstance(existing_options, Mapping):
            for pid, payload in existing_options.items():
                if not isinstance(pid, str):
                    continue
                existing_profiles[pid] = dict(payload)

        count = await async_import_profiles(self.hass, path)
        await self.async_load()

        if count:
            updated_profiles = dict(existing_profiles)
            changed = False
            for pid, profile in self._profiles.items():
                payload = profile.to_json()
                payload.setdefault("name", profile.display_name)
                existing = updated_profiles.get(pid)
                if not isinstance(existing, Mapping) or dict(existing) != payload:
                    updated_profiles[pid] = payload
                    changed = True
            if changed:
                new_opts = dict(self.entry.options)
                new_opts[CONF_PROFILES] = updated_profiles
                self.hass.config_entries.async_update_entry(self.entry, options=new_opts)
                self.entry.options = new_opts

        self.publish_full_snapshot()
        return count

    # ------------------------------------------------------------------
    # Utility helpers primarily for diagnostics
    # ------------------------------------------------------------------
    def summaries(self) -> list[dict[str, Any]]:
        """Return a serialisable summary of all profiles."""

        summaries: list[dict[str, Any]] = []
        for profile in self._profiles.values():
            summary = profile.summary()
            metadata = self._profile_device_metadata(profile.profile_id, summary.get("name"))
            summary["device_identifier"] = metadata["identifier"]
            summary["device_info"] = metadata["info"]
            summaries.append(summary)
        return summaries

    def diagnostics_snapshot(self) -> list[dict[str, Any]]:
        """Return expanded diagnostics data for every profile."""

        snapshot: list[dict[str, Any]] = []
        for profile in self._profiles.values():
            summary = profile.summary()
            metadata = self._profile_device_metadata(profile.profile_id, summary.get("name"))
            summary["device_identifier"] = metadata["identifier"]
            summary["device_info"] = metadata["info"]
            snapshot.append(
                {
                    "plant_id": profile.profile_id,
                    "profile_id": profile.profile_id,
                    "profile_name": summary.get("name"),
                    "summary": summary,
                    "run_history": [event.to_json() for event in profile.run_history],
                    "harvest_history": [event.to_json() for event in profile.harvest_history],
                    "statistics": [stat.to_json() for stat in profile.statistics],
                    "lineage": [entry.to_json() for entry in profile.lineage],
                    "device_identifier": metadata["identifier"],
                    "device_info": metadata["info"],
                }
            )
        return snapshot

    def __iter__(self) -> Iterable[BioProfile]:
        return iter(self._profiles.values())

    def __len__(self) -> int:  # pragma: no cover - trivial
        return len(self._profiles)
