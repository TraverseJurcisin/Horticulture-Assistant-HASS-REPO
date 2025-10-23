from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfTemperature, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_PROFILES, DOMAIN
from .coordinator import HorticultureCoordinator
from .coordinator_ai import HortiAICoordinator
from .coordinator_local import HortiLocalCoordinator
from .derived import (
    PlantDewPointSensor,
    PlantDLISensor,
    PlantMoldRiskSensor,
    PlantPPFDSensor,
    PlantVPDSensor,
)
from .entity import HorticultureEntity
from .irrigation_bridge import PlantIrrigationRecommendationSensor
from .profile.statistics import SUCCESS_STATS_VERSION
from .utils.entry_helpers import get_entry_data, store_entry_data

HORTI_STATUS_DESCRIPTION = SensorEntityDescription(
    key="status",
    translation_key="status",
    device_class=SensorDeviceClass.ENUM,
    entity_category=EntityCategory.DIAGNOSTIC,
    options=["ok", "error"],
)

HORTI_RECOMMENDATION_DESCRIPTION = SensorEntityDescription(
    key="recommendation",
    translation_key="recommendation",
    entity_category=EntityCategory.DIAGNOSTIC,
)


PROFILE_SENSOR_DESCRIPTIONS = {
    "ppfd": SensorEntityDescription(
        key="ppfd",
        translation_key="ppfd",
        native_unit_of_measurement="µmol/m²·s",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:white-balance-sunny",
    ),
    "dli": SensorEntityDescription(
        key="dli",
        translation_key="dli",
        native_unit_of_measurement="mol/m²·day",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:weather-sunny-alert",
    ),
    "vpd": SensorEntityDescription(
        key="vpd",
        translation_key="vpd",
        native_unit_of_measurement="kPa",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:water-percent",
    ),
    "dew_point": SensorEntityDescription(
        key="dew_point",
        translation_key="dew_point",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:thermometer-water",
    ),
    "moisture": SensorEntityDescription(
        key="moisture",
        translation_key="moisture",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.MOISTURE,
        icon="mdi:water-percent",
    ),
    "status": SensorEntityDescription(
        key="status",
        translation_key="status",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        options=["ok", "warn", "critical"],
    ),
}


class CloudSyncSensor(SensorEntity):
    """Base class for cloud sync diagnostic sensors."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_has_entity_name = True
    _attr_should_poll = True
    SCAN_INTERVAL = timedelta(minutes=1)

    def __init__(self, manager, entry_id: str, plant_name: str) -> None:
        self._manager = manager
        self._entry_id = entry_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"cloud:{entry_id}")},
            name=f"{plant_name} Cloud Sync",
            manufacturer="Horticulture Assistant",
            model="Cloud Service",
        )

    # pylint: disable=missing-return-doc
    def _cloud_status(self) -> dict[str, Any]:
        status = self._manager.status()
        configured = bool(status.get("configured"))
        self._attr_available = configured
        return status


class CloudSnapshotAgeSensor(CloudSyncSensor):
    """Expose the age of the freshest cloud snapshot in days."""

    _attr_icon = "mdi:cloud-refresh"
    _attr_native_unit_of_measurement = UnitOfTime.DAYS
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, manager, entry_id: str, plant_name: str) -> None:
        super().__init__(manager, entry_id, plant_name)
        self._attr_unique_id = f"{DOMAIN}_{entry_id}_cloud_snapshot_age"
        self._attr_name = "Cloud Snapshot Age"

    async def async_update(self) -> None:
        status = self._cloud_status()
        age = status.get("cloud_snapshot_age_days")
        self._attr_native_value = round(age, 3) if isinstance(age, int | float) else age
        self._attr_extra_state_attributes = {
            "oldest_age_days": status.get("cloud_snapshot_oldest_age_days"),
            "cloud_cache_entries": status.get("cloud_cache_entries"),
            "last_success_at": status.get("last_success_at"),
            "connection_reason": (status.get("connection") or {}).get("reason"),
        }


class CloudOutboxSensor(CloudSyncSensor):
    """Expose the number of pending events awaiting upload."""

    _attr_icon = "mdi:cloud-upload"
    _attr_native_unit_of_measurement = "events"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, manager, entry_id: str, plant_name: str) -> None:
        super().__init__(manager, entry_id, plant_name)
        self._attr_unique_id = f"{DOMAIN}_{entry_id}_cloud_outbox_events"
        self._attr_name = "Cloud Outbox Size"

    async def async_update(self) -> None:
        status = self._cloud_status()
        outbox = status.get("outbox_size")
        self._attr_native_value = int(outbox) if isinstance(outbox, int | float) else outbox
        connection = status.get("connection") or {}
        self._attr_extra_state_attributes = {
            "last_push_error": status.get("last_push_error"),
            "last_pull_error": status.get("last_pull_error"),
            "connected": connection.get("connected"),
            "local_only": connection.get("local_only"),
        }


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    stored = get_entry_data(hass, entry) or store_entry_data(hass, entry)
    coord_ai: HortiAICoordinator = stored["coordinator_ai"]
    coord_local: HortiLocalCoordinator = stored["coordinator_local"]
    profile_coord: HorticultureCoordinator | None = stored.get("coordinator")
    keep_stale: bool = stored.get("keep_stale", True)
    plant_id: str = stored["plant_id"]
    plant_name: str = stored["plant_name"]

    sensors = [
        HortiStatusSensor(coord_ai, coord_local, entry.entry_id, plant_name, plant_id, keep_stale),
        HortiRecommendationSensor(coord_ai, entry.entry_id, plant_name, plant_id, keep_stale),
        PlantPPFDSensor(hass, entry, plant_name, plant_id),
        PlantDLISensor(hass, entry, plant_name, plant_id),
    ]

    sensors_cfg = entry.options.get("sensors", {})
    if sensors_cfg.get("temperature") and sensors_cfg.get("humidity"):
        sensors.extend(
            [
                PlantVPDSensor(hass, entry, plant_name, plant_id),
                PlantDewPointSensor(hass, entry, plant_name, plant_id),
                PlantMoldRiskSensor(hass, entry, plant_name, plant_id),
            ]
        )

    if sensors_cfg.get("smart_irrigation"):
        sensors.append(PlantIrrigationRecommendationSensor(hass, entry, plant_name, plant_id))

    profiles = entry.options.get(CONF_PROFILES, {})
    registry = stored.get("profile_registry")
    if profile_coord and profiles:
        for pid, profile in profiles.items():
            name = profile.get("name", pid)
            sensors.append(ProfileMetricSensor(profile_coord, pid, name, PROFILE_SENSOR_DESCRIPTIONS["ppfd"]))
            sensors.append(ProfileMetricSensor(profile_coord, pid, name, PROFILE_SENSOR_DESCRIPTIONS["dli"]))
            prof_sensors = profile.get("sensors", {})
            if prof_sensors.get("temperature") and prof_sensors.get("humidity"):
                sensors.append(ProfileMetricSensor(profile_coord, pid, name, PROFILE_SENSOR_DESCRIPTIONS["vpd"]))
                sensors.append(ProfileMetricSensor(profile_coord, pid, name, PROFILE_SENSOR_DESCRIPTIONS["dew_point"]))
            if prof_sensors.get("moisture"):
                sensors.append(ProfileMetricSensor(profile_coord, pid, name, PROFILE_SENSOR_DESCRIPTIONS["moisture"]))
                sensors.append(ProfileMetricSensor(profile_coord, pid, name, PROFILE_SENSOR_DESCRIPTIONS["status"]))
            if registry is not None:
                sensors.append(ProfileSuccessSensor(profile_coord, registry, pid, name))
                sensors.append(ProfileProvenanceSensor(profile_coord, registry, pid, name))

    cloud_manager = stored.get("cloud_sync_manager")
    if cloud_manager:
        sensors.append(CloudSnapshotAgeSensor(cloud_manager, entry.entry_id, plant_name))
        sensors.append(CloudOutboxSensor(cloud_manager, entry.entry_id, plant_name))

    async_add_entities(sensors, True)


class HortiStatusSensor(CoordinatorEntity[HortiAICoordinator], SensorEntity):
    entity_description = HORTI_STATUS_DESCRIPTION
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: HortiAICoordinator,
        local: HortiLocalCoordinator,
        entry_id: str,
        plant_name: str,
        plant_id: str,
        keep_stale: bool,
    ) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_{entry_id}_{self.entity_description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"plant:{plant_id}")},
            name=plant_name,
            manufacturer="Horticulture Assistant",
            model="Plant Profile",
        )
        self._local = local
        self._keep_stale = keep_stale
        self._citations: dict | None = None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if self._local:
            self.async_on_remove(self._local.async_add_listener(self.async_write_ha_state))
        # Load citation summary once on startup
        from .profile.store import async_load_all

        profiles = await async_load_all(self.hass)
        total = 0
        summary: dict[str, int] = {}
        links: list[str] = []
        link_set: set[str] = set()
        latest: datetime | None = None

        def _extract_citations(payload: dict[str, Any]) -> list[dict[str, Any]]:
            citations = payload.get("citations") or []
            if isinstance(citations, list):
                return [c for c in citations if isinstance(c, dict)]
            return []

        for prof in profiles.values():
            resolved = prof.get("resolved_targets") or {}
            if isinstance(resolved, dict):
                for key, data in resolved.items():
                    if not isinstance(data, dict):
                        continue
                    citations = _extract_citations(data)
                    if not citations:
                        continue
                    total += len(citations)
                    summary[str(key)] = summary.get(str(key), 0) + len(citations)
                    for cit in citations:
                        if len(links) >= 3:
                            break
                        url = cit.get("url")
                        if url and url not in link_set:
                            links.append(url)
                            link_set.add(url)

            legacy = prof.get("variables") or {}
            if isinstance(legacy, dict):
                for key, data in legacy.items():
                    if not isinstance(data, dict):
                        continue
                    citations = _extract_citations(data)
                    if not citations:
                        continue
                    total += len(citations)
                    summary[str(key)] = summary.get(str(key), 0) + len(citations)
                    for cit in citations:
                        if len(links) >= 3:
                            break
                        url = cit.get("url")
                        if url and url not in link_set:
                            links.append(url)
                            link_set.add(url)

            lr = prof.get("last_resolved")
            if lr:
                ts = datetime.fromisoformat(lr.replace("Z", "+00:00"))
                if latest is None or ts > latest:
                    latest = ts
        self._citations = {
            "citations_count": total,
            "citations_summary": summary,
            "citations_links_preview": links,
            "last_resolved_utc": latest.isoformat() if latest else None,
        }

    @property
    def native_value(self):
        if not self.coordinator.last_update_success:
            return "error"
        data = self.coordinator.data or {}
        return "ok" if data.get("ok") is True else "error"

    @property
    def extra_state_attributes(self):
        api = getattr(self.coordinator, "api", None)
        last_exc = getattr(self.coordinator, "last_exception_msg", None)
        if not last_exc and self.coordinator.last_exception:
            last_exc = str(self.coordinator.last_exception)
        latency = getattr(api, "last_latency_ms", None)
        if latency is None:
            latency = getattr(self.coordinator, "latency_ms", None)
        attrs = {
            "last_update_success": self.coordinator.last_update_success,
            "last_exception": last_exc,
            "retry_count": max(
                getattr(api, "_failures", 0),
                getattr(self.coordinator, "retry_count", 0),
            ),
            "breaker_open": (
                getattr(api, "_open", True) is False
                if api is not None
                else getattr(self.coordinator, "breaker_open", None)
            ),
            "latency_ms": latency,
        }
        if self._citations:
            attrs.update(self._citations)
        return attrs

    @property
    def available(self) -> bool:
        if self._keep_stale:
            return True
        return super().available


class HortiRecommendationSensor(CoordinatorEntity[HortiAICoordinator], SensorEntity):
    entity_description = HORTI_RECOMMENDATION_DESCRIPTION
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: HortiAICoordinator,
        entry_id: str,
        plant_name: str,
        plant_id: str,
        keep_stale: bool,
    ) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_{entry_id}_{self.entity_description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"plant:{plant_id}")},
            name=plant_name,
            manufacturer="Horticulture Assistant",
            model="Plant Profile",
        )
        self._keep_stale = keep_stale

    @property
    def native_value(self):
        data = self.coordinator.data or {}
        return data.get("recommendation")

    @property
    def available(self) -> bool:
        if self._keep_stale:
            return True
        return super().available


class ProfileMetricSensor(HorticultureEntity, SensorEntity):
    """Generic profile metric sensor backed by the coordinator."""

    entity_description: SensorEntityDescription

    def __init__(
        self,
        coordinator: HorticultureCoordinator,
        profile_id: str,
        profile_name: str,
        description: SensorEntityDescription,
    ) -> None:
        super().__init__(coordinator, profile_id, profile_name)
        self.entity_description = description
        self._attr_unique_id = f"{profile_id}:{description.key}"
        if description.name:
            self._attr_name = description.name

    @property
    def native_value(self):
        return (
            (self.coordinator.data or {})
            .get("profiles", {})
            .get(self._profile_id, {})
            .get("metrics", {})
            .get(self.entity_description.key)
        )


class ProfileSuccessSensor(HorticultureEntity, SensorEntity):
    """Expose the latest success-rate snapshot for a profile."""

    _attr_icon = "mdi:chart-bell-curve-cumulative"
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator: HorticultureCoordinator,
        registry,
        profile_id: str,
        profile_name: str,
    ) -> None:
        super().__init__(coordinator, profile_id, profile_name)
        self._registry = registry
        self._attr_unique_id = f"{profile_id}:success_rate"
        self._attr_name = "Success Rate"

    def _get_profile(self):
        getter = getattr(self._registry, "get_profile", None)
        if getter is None:
            getter = getattr(self._registry, "get", None)
        if getter is None:
            return None
        return getter(self._profile_id)

    def _latest_snapshot(self):
        profile = self._get_profile()
        if profile is None:
            return None
        for snapshot in getattr(profile, "computed_stats", []) or []:
            if snapshot.stats_version == SUCCESS_STATS_VERSION:
                return snapshot
        return None

    @property
    def native_value(self):
        snapshot = self._latest_snapshot()
        if snapshot is None:
            return None
        payload = snapshot.payload if isinstance(snapshot.payload, dict) else {}
        value = payload.get("weighted_success_percent")
        if value is None:
            value = payload.get("average_success_percent")
        if value is None:
            return None
        try:
            return round(float(value), 3)
        except (TypeError, ValueError):
            return None

    @property
    def extra_state_attributes(self):
        snapshot = self._latest_snapshot()
        if snapshot is None:
            return None
        payload = snapshot.payload if isinstance(snapshot.payload, dict) else {}
        attrs: dict[str, Any] = {}
        for key in (
            "samples_recorded",
            "runs_tracked",
            "targets_met",
            "targets_total",
            "stress_events",
            "best_success_percent",
            "worst_success_percent",
        ):
            value = payload.get(key)
            if value is not None:
                attrs[key] = value
        if snapshot.computed_at:
            attrs["computed_at"] = snapshot.computed_at
        contributors = payload.get("contributors")
        if isinstance(contributors, list) and contributors:
            attrs["contributors"] = contributors
        if snapshot.contributions:
            attrs["contribution_weights"] = [contrib.to_json() for contrib in snapshot.contributions]
        return attrs or None


class ProfileProvenanceSensor(HorticultureEntity, SensorEntity):
    """Diagnostic sensor summarising resolved target provenance."""

    _attr_icon = "mdi:source-branch"
    _attr_native_unit_of_measurement = "targets"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: HorticultureCoordinator,
        registry,
        profile_id: str,
        profile_name: str,
    ) -> None:
        super().__init__(coordinator, profile_id, profile_name)
        self._registry = registry
        self._attr_unique_id = f"{profile_id}:provenance"
        self._attr_name = "Target Provenance"

    def _get_profile(self):
        getter = getattr(self._registry, "get_profile", None)
        if getter is None:
            getter = getattr(self._registry, "get", None)
        if getter is None:
            return None
        profile = getter(self._profile_id)
        if profile is not None:
            profile.refresh_sections()
        return profile

    def _provenance_summary(self) -> dict[str, Any] | None:
        profile = self._get_profile()
        if profile is None:
            return None
        return profile.provenance_summary()

    def native_value(self):
        summary = self._provenance_summary()
        if not summary:
            return None
        inherited = [key for key, meta in summary.items() if meta.get("is_inherited")]
        return len(inherited)

    def extra_state_attributes(self):
        profile = self._get_profile()
        if profile is None:
            return None
        summary = profile.provenance_summary()
        detailed = profile.resolved_provenance(
            include_overlay=False,
            include_extras=True,
            include_citations=False,
        )

        inherited: list[str] = []
        overrides: list[str] = []
        external: list[str] = []
        computed: list[str] = []

        for key, meta in summary.items():
            source = str(meta.get("source_type"))
            if meta.get("is_inherited"):
                inherited.append(key)
            elif source in {"manual", "local_override"}:
                overrides.append(key)
            elif source == "computed":
                computed.append(key)
            else:
                external.append(key)

        attrs: dict[str, Any] = {
            "total_targets": len(summary),
            "inherited_count": len(inherited),
            "override_count": len(overrides),
            "external_count": len(external),
            "computed_count": len(computed),
            "inherited_fields": sorted(inherited),
            "override_fields": sorted(overrides),
            "external_fields": sorted(external),
            "computed_fields": sorted(computed),
            "provenance_map": summary,
            "detailed_provenance": detailed,
            "profile_name": profile.display_name,
        }
        if profile.last_resolved:
            attrs["last_resolved"] = profile.last_resolved
        return attrs
