from __future__ import annotations

from contextlib import suppress
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

from .const import (
    CONF_PROFILES,
    DOMAIN,
    FEATURE_AI_ASSIST,
    FEATURE_CLOUD_SYNC,
    FEATURE_IRRIGATION_AUTOMATION,
)
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
from .entitlements import derive_entitlements
from .entity import HorticultureEntity
from .irrigation_bridge import PlantIrrigationRecommendationSensor
from .profile.statistics import (
    EVENT_STATS_VERSION,
    NUTRIENT_STATS_VERSION,
    SUCCESS_STATS_VERSION,
    YIELD_STATS_VERSION,
)
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
    "vpd_7d_avg": SensorEntityDescription(
        key="vpd_7d_avg",
        translation_key="vpd_7d_avg",
        native_unit_of_measurement="kPa",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:chart-line-variant",
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
            "manual_sync_last_run": (status.get("manual_sync") or {}).get("last_run_at"),
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
        offline_queue = status.get("offline_queue") or {}
        self._attr_extra_state_attributes = {
            "last_push_error": status.get("last_push_error"),
            "last_pull_error": status.get("last_pull_error"),
            "connected": connection.get("connected"),
            "local_only": connection.get("local_only"),
            "offline_queue_reason": offline_queue.get("reason"),
            "offline_queue_last_enqueued_at": offline_queue.get("last_enqueued_at"),
            "offline_queue_last_error": offline_queue.get("last_error"),
        }


class CloudConnectionSensor(CloudSyncSensor):
    """Summarise the current cloud connection state."""

    _attr_icon = "mdi:cloud-check"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, manager, entry_id: str, plant_name: str) -> None:
        super().__init__(manager, entry_id, plant_name)
        self._attr_unique_id = f"{DOMAIN}_{entry_id}_cloud_connection"
        self._attr_name = "Cloud Connection"

    async def async_update(self) -> None:
        status = self._cloud_status()
        connection = status.get("connection") or {}
        if not status.get("enabled"):
            value = "disabled"
        elif not status.get("configured"):
            value = "not_configured"
        elif connection.get("connected"):
            value = "connected"
        elif connection.get("local_only"):
            value = str(connection.get("reason") or "local_only")
        else:
            value = "unknown"
        self._attr_native_value = value
        attrs = {
            "reason": connection.get("reason"),
            "local_only": connection.get("local_only"),
            "last_success_at": connection.get("last_success_at") or status.get("last_success_at"),
            "account_email": status.get("account_email"),
            "tenant_id": status.get("tenant_id"),
            "roles": status.get("roles"),
            "organization_id": status.get("organization_id"),
            "organization_name": status.get("organization_name"),
            "organization_role": status.get("organization_role"),
            "available_organizations": status.get("organizations"),
            "manual_sync_last_run": (status.get("manual_sync") or {}).get("last_run_at"),
            "manual_sync_error": (status.get("manual_sync") or {}).get("error"),
            "token_expires_at": status.get("token_expires_at"),
            "token_expires_in_seconds": status.get("token_expires_in_seconds"),
            "token_expired": status.get("token_expired"),
            "refresh_token_available": status.get("refresh_token"),
        }
        self._attr_extra_state_attributes = {k: v for k, v in attrs.items() if v is not None}


class GardenSummarySensor(CoordinatorEntity[HorticultureCoordinator], SensorEntity):
    """Aggregate health insights across all configured profiles."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:sprout"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_native_unit_of_measurement = "profiles"
    _attr_translation_key = "garden_summary"

    def __init__(self, coordinator: HorticultureCoordinator, entry_id: str, label: str) -> None:
        super().__init__(coordinator)
        friendly = label or "Garden"
        self._attr_unique_id = f"{DOMAIN}_{entry_id}_garden_summary"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"garden:{entry_id}")},
            name=f"{friendly} Garden Overview",
            manufacturer="Horticulture Assistant",
            model="Garden Summary",
        )

    @property
    def native_value(self):
        summary = (self.coordinator.data or {}).get("summary") or {}
        problems = summary.get("problem_profiles")
        return problems if isinstance(problems, int | float) else 0

    @property
    def extra_state_attributes(self):
        summary = (self.coordinator.data or {}).get("summary")
        if not summary:
            return None
        attrs = {k: v for k, v in summary.items() if k != "status_counts"}
        counts = summary.get("status_counts") or {}
        for key, value in counts.items():
            attrs[f"status_{key}"] = value
        return attrs


class EntitlementSummarySensor(SensorEntity):
    """Expose the current feature entitlements derived from the config entry."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_has_entity_name = True
    _attr_icon = "mdi:lock-check"
    _attr_should_poll = True
    SCAN_INTERVAL = timedelta(minutes=5)

    def __init__(self, entry: ConfigEntry) -> None:
        self._entry = entry
        self._attr_unique_id = f"{DOMAIN}_{entry.entry_id}_feature_entitlements"
        self._attr_name = "Feature entitlements"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"account:{entry.entry_id}")},
            name="PhenoLogic Account",
            manufacturer="Horticulture Assistant",
            model="Cloud Account",
        )

    async def async_update(self) -> None:
        entitlements = derive_entitlements(self._entry.options)
        features = sorted(entitlements.features)
        if FEATURE_AI_ASSIST in features or FEATURE_IRRIGATION_AUTOMATION in features:
            state = "premium"
        elif FEATURE_CLOUD_SYNC in features:
            state = "cloud"
        else:
            state = "local"
        self._attr_native_value = state
        self._attr_extra_state_attributes = {
            "features": features,
            "roles": list(entitlements.roles),
            "organization_role": entitlements.organization_role,
            "organization_id": entitlements.organization_id,
            "account_email": entitlements.account_email,
            "source": entitlements.source,
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

    sensors.append(EntitlementSummarySensor(entry))

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
    if profile_coord:
        sensors.append(GardenSummarySensor(profile_coord, entry.entry_id, plant_name))
    if profile_coord and profiles:
        for pid, profile in profiles.items():
            name = profile.get("name", pid)
            sensors.append(ProfileMetricSensor(profile_coord, pid, name, PROFILE_SENSOR_DESCRIPTIONS["ppfd"]))
            sensors.append(ProfileMetricSensor(profile_coord, pid, name, PROFILE_SENSOR_DESCRIPTIONS["dli"]))
            prof_sensors = profile.get("sensors", {})
            if prof_sensors.get("temperature") and prof_sensors.get("humidity"):
                sensors.append(ProfileMetricSensor(profile_coord, pid, name, PROFILE_SENSOR_DESCRIPTIONS["vpd"]))
                sensors.append(ProfileMetricSensor(profile_coord, pid, name, PROFILE_SENSOR_DESCRIPTIONS["dew_point"]))
                sensors.append(
                    ProfileMetricSensor(
                        profile_coord,
                        pid,
                        name,
                        PROFILE_SENSOR_DESCRIPTIONS["vpd_7d_avg"],
                    )
                )
            if prof_sensors.get("moisture"):
                sensors.append(ProfileMetricSensor(profile_coord, pid, name, PROFILE_SENSOR_DESCRIPTIONS["moisture"]))
                sensors.append(ProfileMetricSensor(profile_coord, pid, name, PROFILE_SENSOR_DESCRIPTIONS["status"]))
            if registry is not None:
                sensors.append(ProfileSuccessSensor(profile_coord, registry, pid, name))
                sensors.append(ProfileYieldSensor(profile_coord, registry, pid, name))
                sensors.append(ProfileEventSensor(profile_coord, registry, pid, name))
                sensors.append(ProfileProvenanceSensor(profile_coord, registry, pid, name))
                sensors.append(ProfileRunStatusSensor(profile_coord, registry, pid, name))
                sensors.append(ProfileFeedingSensor(profile_coord, registry, pid, name))

    cloud_manager = stored.get("cloud_sync_manager")
    if cloud_manager:
        sensors.append(CloudSnapshotAgeSensor(cloud_manager, entry.entry_id, plant_name))
        sensors.append(CloudOutboxSensor(cloud_manager, entry.entry_id, plant_name))
        sensors.append(CloudConnectionSensor(cloud_manager, entry.entry_id, plant_name))

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


class ProfileYieldSensor(HorticultureEntity, SensorEntity):
    """Expose cumulative yield totals for a profile."""

    _attr_icon = "mdi:scale"
    _attr_native_unit_of_measurement = "g"
    _attr_state_class = SensorStateClass.TOTAL

    def __init__(
        self,
        coordinator: HorticultureCoordinator,
        registry,
        profile_id: str,
        profile_name: str,
    ) -> None:
        super().__init__(coordinator, profile_id, profile_name)
        self._registry = registry
        self._attr_unique_id = f"{profile_id}:yield_total"
        self._attr_name = "Yield Total"

    def _get_profile(self):
        getter = getattr(self._registry, "get_profile", None)
        if getter is None:
            getter = getattr(self._registry, "get", None)
        if getter is None:
            return None
        return getter(self._profile_id)

    def _yield_snapshot(self):
        profile = self._get_profile()
        if profile is None:
            return None
        for snapshot in getattr(profile, "computed_stats", []) or []:
            if snapshot.stats_version == YIELD_STATS_VERSION:
                return snapshot
        return None

    @property
    def native_value(self):
        snapshot = self._yield_snapshot()
        if snapshot is None:
            return None
        payload = snapshot.payload if isinstance(snapshot.payload, dict) else {}
        metrics = payload.get("metrics") or {}
        total = metrics.get("total_yield_grams")
        if total is None:
            yields_payload = payload.get("yields") or {}
            total = yields_payload.get("total_grams")
        if total is None:
            return None
        try:
            return round(float(total), 3)
        except (TypeError, ValueError):
            return None

    @property
    def extra_state_attributes(self):
        snapshot = self._yield_snapshot()
        if snapshot is None:
            return None
        payload = snapshot.payload if isinstance(snapshot.payload, dict) else {}
        metrics = payload.get("metrics") or {}
        attrs: dict[str, Any] = {}
        for key in (
            "harvest_count",
            "average_yield_grams",
            "average_yield_density_g_m2",
            "mean_density_g_m2",
            "total_area_m2",
            "days_since_last_harvest",
            "total_fruit_count",
        ):
            value = metrics.get(key)
            if value is not None:
                attrs[key] = value
        if metrics.get("average_yield_grams") is not None:
            with suppress(TypeError, ValueError):
                attrs["average_yield_kilograms"] = round(
                    float(metrics["average_yield_grams"]) / 1000,
                    3,
                )
        if metrics.get("average_yield_density_g_m2") is not None:
            with suppress(TypeError, ValueError):
                attrs["average_yield_density_kg_m2"] = round(
                    float(metrics["average_yield_density_g_m2"]) / 1000,
                    3,
                )
        if metrics.get("mean_density_g_m2") is not None:
            with suppress(TypeError, ValueError):
                attrs["mean_density_kg_m2"] = round(
                    float(metrics["mean_density_g_m2"]) / 1000,
                    3,
                )
        yields_payload = payload.get("yields") or {}
        for key in ("total_grams", "total_area_m2"):
            if yields_payload.get(key) is not None:
                attrs.setdefault(key, yields_payload.get(key))
        if yields_payload.get("total_grams") is not None:
            with suppress(TypeError, ValueError):
                attrs["total_kilograms"] = round(
                    float(yields_payload["total_grams"]) / 1000,
                    3,
                )
        if yields_payload.get("total_fruit_count") is not None:
            attrs.setdefault("total_fruit_count", yields_payload.get("total_fruit_count"))
        densities_payload = payload.get("densities") or {}
        for key, value in densities_payload.items():
            if value is not None:
                attrs[f"density_{key}"] = value
                with suppress(TypeError, ValueError):
                    attrs[f"density_{key}_kg_m2"] = round(float(value) / 1000, 3)
        if payload.get("runs_tracked") is not None:
            attrs["runs_tracked"] = payload.get("runs_tracked")
        if payload.get("contributors"):
            attrs["contributors"] = payload.get("contributors")
        if payload.get("window_totals"):
            attrs["window_totals"] = payload["window_totals"]
        if payload.get("last_harvest_at"):
            attrs["last_harvest_at"] = payload["last_harvest_at"]
        if payload.get("days_since_last_harvest") is not None:
            attrs.setdefault("days_since_last_harvest", payload.get("days_since_last_harvest"))
        if snapshot.computed_at:
            attrs["computed_at"] = snapshot.computed_at
        return {k: v for k, v in attrs.items() if v is not None}


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
        badges = profile.provenance_badges()

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
        if badges:
            attrs["badges"] = badges
            attrs["badge_counts"] = {
                "inherited": sum(1 for meta in badges.values() if meta.get("badge") == "inherited"),
                "override": sum(1 for meta in badges.values() if meta.get("badge") == "override"),
                "external": sum(1 for meta in badges.values() if meta.get("badge") == "external"),
                "computed": sum(1 for meta in badges.values() if meta.get("badge") == "computed"),
            }
        if profile.last_resolved:
            attrs["last_resolved"] = profile.last_resolved
        return attrs


class ProfileRunStatusSensor(HorticultureEntity, SensorEntity):
    """Expose lifecycle run information for a profile."""

    _attr_icon = "mdi:timeline-clock-outline"
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
        self._attr_unique_id = f"{profile_id}:run_status"
        self._attr_name = "Run Status"

    def _get_profile(self):
        getter = getattr(self._registry, "get_profile", None)
        if getter is None:
            getter = getattr(self._registry, "get", None)
        if getter is None:
            return None
        return getter(self._profile_id)

    def _latest_run(self):
        profile = self._get_profile()
        if profile is None:
            return None
        runs = profile.run_summaries()
        if not runs:
            return None
        return runs[0]

    @property
    def native_value(self):
        summary = self._latest_run()
        if summary is None:
            return "idle"
        return summary.get("status") or "unknown"

    @property
    def extra_state_attributes(self):
        summary = self._latest_run()
        if summary is None:
            return None
        attrs: dict[str, Any] = {
            "run_id": summary.get("run_id"),
            "started_at": summary.get("started_at"),
            "ended_at": summary.get("ended_at"),
            "duration_days": summary.get("duration_days"),
            "harvest_count": summary.get("harvest_count"),
            "yield_grams": summary.get("yield_grams"),
            "yield_density_g_m2": summary.get("yield_density_g_m2"),
            "mean_yield_density_g_m2": summary.get("mean_yield_density_g_m2"),
            "success_rate": summary.get("success_rate"),
            "targets_met": summary.get("targets_met"),
            "targets_total": summary.get("targets_total"),
            "stress_events": summary.get("stress_events"),
        }
        if summary.get("environment"):
            attrs["environment"] = summary["environment"]
        if summary.get("metadata"):
            attrs["metadata"] = summary["metadata"]
        return {k: v for k, v in attrs.items() if v is not None}


class ProfileFeedingSensor(HorticultureEntity, SensorEntity):
    """Expose nutrient application cadence for a profile."""

    _attr_icon = "mdi:cup-water"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_native_unit_of_measurement = UnitOfTime.DAYS
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
        self._attr_unique_id = f"{profile_id}:feeding_status"
        self._attr_name = "Feeding Status"

    def _get_profile(self):
        getter = getattr(self._registry, "get_profile", None)
        if getter is None:
            getter = getattr(self._registry, "get", None)
        if getter is None:
            return None
        return getter(self._profile_id)

    def _snapshot(self) -> tuple[dict[str, Any] | None, str | None]:
        profile = self._get_profile()
        if profile is None:
            return None, None
        for snapshot in getattr(profile, "computed_stats", []) or []:
            if snapshot.stats_version == NUTRIENT_STATS_VERSION:
                payload = snapshot.payload if isinstance(snapshot.payload, dict) else {}
                return payload, snapshot.computed_at
        return None, None

    @property
    def native_value(self):
        payload, _computed = self._snapshot()
        if not payload:
            return None
        metrics = payload.get("metrics") or {}
        value = metrics.get("days_since_last_event")
        if value is None:
            return None
        try:
            return round(float(value), 3)
        except (TypeError, ValueError):
            return None

    @property
    def extra_state_attributes(self):
        payload, computed = self._snapshot()
        if not payload:
            return None
        attrs: dict[str, Any] = {}
        if payload.get("scope"):
            attrs["scope"] = payload["scope"]
        metrics = payload.get("metrics")
        if metrics:
            attrs["metrics"] = metrics
        last_event = payload.get("last_event")
        if last_event:
            attrs["last_event"] = last_event
        if payload.get("product_usage"):
            attrs["product_usage"] = payload["product_usage"]
        if payload.get("window_counts"):
            attrs["window_counts"] = payload["window_counts"]
        if payload.get("intervals"):
            attrs["intervals"] = payload["intervals"]
        if payload.get("runs_touched"):
            attrs["runs_touched"] = payload["runs_touched"]
        if computed:
            attrs["computed_at"] = computed
        return attrs


class ProfileEventSensor(HorticultureEntity, SensorEntity):
    """Summarise cultivation events for a profile."""

    _attr_icon = "mdi:calendar-clock"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_native_unit_of_measurement = "events"
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
        self._attr_unique_id = f"{profile_id}:event_activity"
        self._attr_name = "Event Activity"

    def _get_profile(self):
        getter = getattr(self._registry, "get_profile", None)
        if getter is None:
            getter = getattr(self._registry, "get", None)
        if getter is None:
            return None
        return getter(self._profile_id)

    def _snapshot(self) -> tuple[dict[str, Any] | None, str | None]:
        profile = self._get_profile()
        if profile is None:
            return None, None
        for snapshot in getattr(profile, "computed_stats", []) or []:
            if snapshot.stats_version == EVENT_STATS_VERSION:
                payload = snapshot.payload if isinstance(snapshot.payload, dict) else {}
                return payload, snapshot.computed_at
        return None, None

    @property
    def native_value(self):
        payload, _computed = self._snapshot()
        if not payload:
            return None
        metrics = payload.get("metrics") or {}
        total = metrics.get("total_events")
        if total is None:
            return None
        try:
            return int(total)
        except (TypeError, ValueError):
            return None

    @property
    def extra_state_attributes(self):
        payload, computed = self._snapshot()
        if not payload:
            return None
        attrs: dict[str, Any] = {}
        metrics = payload.get("metrics") or {}
        for key in ("unique_event_types", "unique_runs", "days_since_last_event"):
            if metrics.get(key) is not None:
                attrs[key] = metrics.get(key)
        if payload.get("last_event"):
            attrs["last_event"] = payload["last_event"]
        if payload.get("event_types"):
            attrs["event_types"] = payload["event_types"]
        if payload.get("top_tags"):
            attrs["top_tags"] = payload["top_tags"]
        if payload.get("runs_touched"):
            attrs["runs_touched"] = payload["runs_touched"]
        if payload.get("window_counts"):
            attrs["window_counts"] = payload["window_counts"]
        if computed:
            attrs["computed_at"] = computed
        return attrs or None
