from __future__ import annotations

import inspect
import logging
from collections import defaultdict
from collections.abc import Iterable, Mapping
from contextlib import suppress
from datetime import datetime, timedelta
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorEntityDescription, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfTemperature, UnitOfTime
from homeassistant.core import (
    CALLBACK_TYPE,
    Event,
    EventStateChangedData,
    HomeAssistant,
    callback,
)
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_PLANT_NAME,
    CONF_PROFILES,
    DOMAIN,
    FEATURE_AI_ASSIST,
    FEATURE_CLOUD_SYNC,
    FEATURE_IRRIGATION_AUTOMATION,
    PLANT_SENSOR_TYPES,
    signal_profile_contexts_updated,
)
from .coordinator import HorticultureCoordinator
from .coordinator_ai import HortiAICoordinator
from .coordinator_local import HortiLocalCoordinator
from .derived import PlantDewPointSensor, PlantDLISensor, PlantMoldRiskSensor, PlantPPFDSensor, PlantVPDSensor
from .entitlements import derive_entitlements
from .entity import HorticultureEntity
from .entity_base import HorticultureBaseEntity, HorticultureEntryEntity, ProfileContextEntityMixin
from .irrigation_bridge import PlantIrrigationRecommendationSensor
from .profile.statistics import EVENT_STATS_VERSION, NUTRIENT_STATS_VERSION, SUCCESS_STATS_VERSION, YIELD_STATS_VERSION
from .profile_monitor import ProfileMonitor
from .utils.entry_helpers import ProfileContext, resolve_profile_context_collection

_LOGGER = logging.getLogger(__name__)

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

PROFILE_SENSOR_SUFFIXES = set(PROFILE_SENSOR_DESCRIPTIONS)
PROFILE_AGGREGATE_SUFFIXES = {
    "success_rate",
    "yield_total",
    "event_activity",
    "provenance",
    "run_status",
    "feeding_status",
}

PROFILE_METRIC_CATEGORIES: tuple[str, ...] = (
    "resolved_targets",
    "targets",
    "variables",
    "thresholds",
)


class PlantProfileSensor(SensorEntity):
    """Sensor representing a plant profile measurement (e.g., soil moisture)."""

    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        config_entry: ConfigEntry,
        sensor_type: str,
        profile_name: str,
        info: Mapping[str, Any],
    ) -> None:
        """Initialize the plant profile sensor entity."""

        self._entry_id = config_entry.entry_id
        self._sensor_type = sensor_type
        self._profile_name = profile_name
        self._attr_name = f"{profile_name} {info.get('name', sensor_type)}"
        self._attr_unique_id = f"{config_entry.entry_id}_{sensor_type}"
        self._linked_entity_id: str | None = None
        self._unsub_tracker: CALLBACK_TYPE | None = None
        self._attr_native_value: float | str | None = None

        device_class = info.get("device_class")
        if isinstance(device_class, SensorDeviceClass):
            self._attr_device_class = device_class
        elif isinstance(device_class, str):
            with suppress(AttributeError):
                self._attr_device_class = getattr(SensorDeviceClass, device_class.upper())
            if not getattr(self, "_attr_device_class", None):
                self._attr_device_class = device_class

        unit = info.get("unit")
        if isinstance(unit, str):
            self._attr_native_unit_of_measurement = unit

        icon = info.get("icon")
        if isinstance(icon, str):
            self._attr_icon = icon

        data_linked = config_entry.data.get("linked_sensors")
        options_linked = config_entry.options.get("linked_sensors")
        if isinstance(data_linked, Mapping) and sensor_type in data_linked:
            self._linked_entity_id = data_linked[sensor_type]
        elif isinstance(options_linked, Mapping) and sensor_type in options_linked:
            self._linked_entity_id = options_linked[sensor_type]
        elif isinstance(data_linked, Mapping) or isinstance(options_linked, Mapping):
            aliases: Mapping[str, tuple[str, ...]] = {
                "soil_moisture": ("moisture",),
                "light": ("illuminance", "lux"),
                "soil_conductivity": ("conductivity", "ec"),
                "battery_level": ("battery",),
                "soil_temperature": ("temperature", "soil_temp", "root_temperature"),
            }
            fallback_keys = aliases.get(sensor_type)
            if fallback_keys:
                for key in fallback_keys:
                    if isinstance(data_linked, Mapping) and key in data_linked:
                        self._linked_entity_id = data_linked[key]
                        break
                    if isinstance(options_linked, Mapping) and key in options_linked:
                        self._linked_entity_id = options_linked[key]
                        break

    @property
    def extra_state_attributes(self) -> Mapping[str, Any]:
        """Return extra attributes including linked sensor reference."""

        return {"linked_sensor": self._linked_entity_id}

    @property
    def sensor_type(self) -> str:
        """Return the plant sensor type key (e.g. air_temperature)."""

        return self._sensor_type

    @property
    def device_info(self) -> Mapping[str, Any]:
        """Return device info to attach this sensor to the plant profile device."""

        return {
            "identifiers": {(DOMAIN, self._entry_id)},
            "name": self._profile_name,
            "manufacturer": "Horticulture Assistant",
            "model": "Plant Profile",
        }

    async def async_added_to_hass(self) -> None:
        """Register callbacks once entity is added to Home Assistant."""

        await super().async_added_to_hass()
        domain_data = self.hass.data.setdefault(DOMAIN, {})
        entities = domain_data.setdefault("entities", {})
        entities[self.unique_id] = self

        if self._linked_entity_id:
            state = self.hass.states.get(self._linked_entity_id)
            if state and state.state not in (None, "unknown", "unavailable"):
                try:
                    self._attr_native_value = float(state.state)
                except ValueError:
                    self._attr_native_value = state.state
                unit = state.attributes.get("unit_of_measurement")
                if unit:
                    self._attr_native_unit_of_measurement = unit
            self._unsub_tracker = async_track_state_change_event(
                self.hass,
                [self._linked_entity_id],
                self._async_sensor_state_changed,
            )
        self.async_write_ha_state()

    async def async_will_remove_from_hass(self) -> None:
        """Cleanup when entity is about to be removed."""

        await super().async_will_remove_from_hass()
        domain_data = self.hass.data.get(DOMAIN, {})
        entities = domain_data.get("entities", {})
        entities.pop(self.unique_id, None)
        if self._unsub_tracker:
            self._unsub_tracker()
            self._unsub_tracker = None

    @callback
    def _async_sensor_state_changed(self, event: Event[EventStateChangedData] | None) -> None:
        """Handle state changes of the linked physical sensor."""

        new_state = event.data.get("new_state") if event else None
        if not new_state:
            return
        if new_state.state in ("unknown", "unavailable"):
            self._attr_native_value = None
        else:
            try:
                self._attr_native_value = float(new_state.state)
            except ValueError:
                self._attr_native_value = new_state.state
        unit = new_state.attributes.get("unit_of_measurement")
        if unit:
            self._attr_native_unit_of_measurement = unit
        self.async_write_ha_state()

    async def set_linked_sensor(self, new_entity_id: str | None) -> None:
        """Link this plant profile sensor to a new physical sensor entity."""

        if self._unsub_tracker:
            self._unsub_tracker()
            self._unsub_tracker = None
        self._linked_entity_id = new_entity_id

        if new_entity_id:
            self._unsub_tracker = async_track_state_change_event(
                self.hass, [new_entity_id], self._async_sensor_state_changed
            )
            state = self.hass.states.get(new_entity_id)
            if state and state.state not in (None, "unknown", "unavailable"):
                try:
                    self._attr_native_value = float(state.state)
                except ValueError:
                    self._attr_native_value = state.state
                unit = state.attributes.get("unit_of_measurement")
                if unit:
                    self._attr_native_unit_of_measurement = unit
            else:
                self._attr_native_value = None
        else:
            self._attr_native_value = None

        self.async_write_ha_state()


class PlantStatusSensor(ProfileContextEntityMixin, HorticultureBaseEntity, SensorEntity):
    """Summarise the overall health of a plant profile."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "plant_status"
    _attr_has_entity_name = True

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, context) -> None:
        ProfileContextEntityMixin.__init__(self, hass, entry, context)
        HorticultureBaseEntity.__init__(
            self,
            entry.entry_id,
            context.name,
            context.profile_id,
            model="Plant Profile",
        )
        self._entry_id = entry.entry_id
        self._monitor: ProfileMonitor | None = ProfileMonitor(hass, context)
        self._attr_unique_id = self.profile_unique_id("health")
        self._attr_icon = "mdi:sprout"

    async def async_update(self) -> None:
        if self._monitor is None:
            self._attr_native_value = None
            self._attr_extra_state_attributes = {}
            return
        result = self._monitor.evaluate()
        self._attr_native_value = result.health
        icon_map = {
            "ok": "mdi:sprout",
            "attention": "mdi:alert-circle-outline",
            "problem": "mdi:alert-circle",
        }
        self._attr_icon = icon_map.get(result.health, "mdi:sprout")
        self._attr_extra_state_attributes = result.as_attributes()

    def _handle_context_updated(self, context: ProfileContext) -> None:
        super()._handle_context_updated(context)
        self._monitor = ProfileMonitor(self.hass, context)
        self._attr_available = True
        scheduler = getattr(self, "async_schedule_update_ha_state", None)
        if callable(scheduler):
            scheduler(True)
        else:
            self.async_write_ha_state()

    def _handle_context_removed(self) -> None:
        self._monitor = None
        super()._handle_context_removed()


class PlantLastSampleSensor(ProfileContextEntityMixin, HorticultureBaseEntity, SensorEntity):
    """Expose the freshest timestamp seen for a plant profile sensor."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_translation_key = "plant_last_sample"
    _attr_has_entity_name = True

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, context) -> None:
        ProfileContextEntityMixin.__init__(self, hass, entry, context)
        HorticultureBaseEntity.__init__(
            self,
            entry.entry_id,
            context.name,
            context.profile_id,
            model="Plant Profile",
        )
        self._monitor: ProfileMonitor | None = ProfileMonitor(hass, context)
        self._attr_unique_id = self.profile_unique_id("last_sample")

    async def async_update(self) -> None:
        if self._monitor is None:
            self._attr_native_value = None
            self._attr_extra_state_attributes = {"issues": [], "sensor_count": 0}
            return
        result = self._monitor.evaluate()
        self._attr_native_value = result.last_sample_at
        self._attr_extra_state_attributes = {
            "issues": [issue.as_dict() for issue in result.issues],
            "sensor_count": len(result.sensors),
        }

    def _handle_context_updated(self, context: ProfileContext) -> None:
        super()._handle_context_updated(context)
        self._monitor = ProfileMonitor(self.hass, context)
        self._attr_available = True
        scheduler = getattr(self, "async_schedule_update_ha_state", None)
        if callable(scheduler):
            scheduler(True)
        else:
            self.async_write_ha_state()

    def _handle_context_removed(self) -> None:
        self._monitor = None
        super()._handle_context_removed()


class CloudSyncSensor(HorticultureEntryEntity, SensorEntity):
    """Base class for cloud sync diagnostic sensors."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_has_entity_name = True
    _attr_should_poll = True
    SCAN_INTERVAL = timedelta(minutes=1)

    def __init__(self, manager, entry_id: str, plant_name: str) -> None:
        HorticultureEntryEntity.__init__(self, entry_id, default_device_name=plant_name)
        self._manager = manager
        self._entry_id = entry_id

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


class GardenSummarySensor(HorticultureEntryEntity, CoordinatorEntity[HorticultureCoordinator], SensorEntity):
    """Aggregate health insights across all configured profiles."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:sprout"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_native_unit_of_measurement = "profiles"
    _attr_translation_key = "garden_summary"

    def __init__(self, coordinator: HorticultureCoordinator, entry_id: str, label: str) -> None:
        CoordinatorEntity.__init__(self, coordinator)
        HorticultureEntryEntity.__init__(self, entry_id, default_device_name=label)
        self._attr_unique_id = f"{DOMAIN}_{entry_id}_garden_summary"

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


class EntitlementSummarySensor(HorticultureEntryEntity, SensorEntity):
    """Expose the current feature entitlements derived from the config entry."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_has_entity_name = True
    _attr_icon = "mdi:lock-check"
    _attr_should_poll = True
    SCAN_INTERVAL = timedelta(minutes=5)

    def __init__(self, entry: ConfigEntry, plant_name: str | None = None) -> None:
        device_name = plant_name or entry.title or entry.entry_id
        HorticultureEntryEntity.__init__(self, entry.entry_id, default_device_name=device_name)
        self._entry = entry
        self._attr_unique_id = f"{DOMAIN}_{entry.entry_id}_feature_entitlements"
        self._attr_name = "Feature entitlements"

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
    collection = resolve_profile_context_collection(hass, entry)
    stored = collection.stored
    contexts = collection.contexts

    hass.data.setdefault(DOMAIN, {}).setdefault("entities", {})

    profile_name = entry.title or stored.get("plant_name") or entry.data.get(CONF_PLANT_NAME)
    profile_sensors = [
        PlantProfileSensor(entry, sensor_type, profile_name or entry.entry_id, info)
        for sensor_type, info in PLANT_SENSOR_TYPES.items()
    ]

    if not contexts:
        _LOGGER.debug("No plant profiles configured; skipping horticulture_assistant sensors")
        if profile_sensors:
            async_add_entities(profile_sensors)
        return

    coord_ai: HortiAICoordinator = stored["coordinator_ai"]
    coord_local: HortiLocalCoordinator = stored["coordinator_local"]
    profile_coord: HorticultureCoordinator | None = stored.get("coordinator")
    keep_stale: bool = stored.get("keep_stale", True)

    entity_registry = er.async_get(hass)
    for entity_entry in er.async_entries_for_config_entry(entity_registry, entry.entry_id):
        if entity_entry.domain != "sensor" or entity_entry.platform != DOMAIN:
            continue
        unique_id = entity_entry.unique_id
        if not isinstance(unique_id, str) or unique_id.startswith(f"{DOMAIN}_{entry.entry_id}_"):
            continue
        if ":" not in unique_id:
            continue
        profile_id, suffix = unique_id.rsplit(":", 1)
        if suffix not in PROFILE_SENSOR_SUFFIXES | PROFILE_AGGREGATE_SUFFIXES:
            continue
        new_unique_id = f"{profile_id}_{suffix}"
        if new_unique_id == unique_id:
            continue
        entity_registry.async_update_entity(entity_entry.entity_id, new_unique_id=new_unique_id)

    profile_ids = set(contexts)
    prefix = f"{DOMAIN}_{entry.entry_id}_"
    for entity_entry in er.async_entries_for_config_entry(entity_registry, entry.entry_id):
        unique_id = entity_entry.unique_id
        if not isinstance(unique_id, str) or not unique_id.startswith(prefix):
            continue
        remainder = unique_id.removeprefix(prefix)
        if not any(remainder.startswith(f"{pid}_") for pid in profile_ids):
            continue
        if remainder == unique_id:
            continue
        entity_registry.async_update_entity(entity_entry.entity_id, new_unique_id=remainder)

    primary_context = collection.primary
    plant_id = primary_context.profile_id
    plant_name = primary_context.name

    known_metric_keys: dict[str, set[tuple[str, str]]] = defaultdict(set)
    known_context_signatures: dict[str, set[str]] = defaultdict(set)

    def _sensor_signature(sensor: SensorEntity) -> str:
        unique_id = getattr(sensor, "unique_id", None)
        if isinstance(unique_id, str) and unique_id:
            return unique_id
        entity_id = getattr(sensor, "entity_id", None)
        if isinstance(entity_id, str) and entity_id:
            return f"entity:{entity_id}"
        return f"{sensor.__class__.__module__}.{sensor.__class__.__qualname__}"

    def _build_metric_value_sensors(
        context: ProfileContext,
    ) -> list[tuple[ProfileMetricValueSensor, tuple[str, str]]]:
        sensors: list[tuple[ProfileMetricValueSensor, tuple[str, str]]] = []
        metrics = context.metrics
        if not isinstance(metrics, Mapping):
            return sensors
        for category in PROFILE_METRIC_CATEGORIES:
            bucket = metrics.get(category)
            if not isinstance(bucket, Mapping):
                continue
            for key, meta in bucket.items():
                if not isinstance(meta, Mapping):
                    continue
                value = meta.get("value")
                if value is None:
                    continue
                sensor = ProfileMetricValueSensor(
                    hass,
                    entry,
                    context,
                    category,
                    key,
                    meta,
                )
                sensors.append((sensor, (category, key)))
        return sensors

    def _build_context_sensors(
        context: ProfileContext,
    ) -> tuple[list[SensorEntity], list[tuple[ProfileMetricValueSensor, tuple[str, str]]]]:
        context_sensors: list[SensorEntity] = [
            PlantStatusSensor(hass, entry, context),
            PlantLastSampleSensor(hass, entry, context),
            PlantPPFDSensor(hass, entry, context),
            PlantDLISensor(hass, entry, context),
        ]
        if context.has_all_sensors("temperature", "humidity"):
            context_sensors.extend(
                [
                    PlantVPDSensor(hass, entry, context),
                    PlantDewPointSensor(hass, entry, context),
                    PlantMoldRiskSensor(hass, entry, context),
                ]
            )
        if context.has_sensors("smart_irrigation"):
            context_sensors.append(PlantIrrigationRecommendationSensor(hass, entry, context))
        metric_pairs = _build_metric_value_sensors(context)
        return context_sensors, metric_pairs

    def _profiles_map() -> Mapping[str, Mapping[str, Any]]:
        profiles = entry.options.get(CONF_PROFILES, {})
        if isinstance(profiles, Mapping):
            return profiles
        return {}

    def _build_profile_option_sensors(
        coordinator: HorticultureCoordinator | None,
        profile_registry,
        contexts_map: Mapping[str, ProfileContext],
        profiles_map: Mapping[str, Mapping[str, Any]],
        profile_id: str,
    ) -> list[SensorEntity]:
        if coordinator is None:
            return []
        profile = profiles_map.get(profile_id)
        if not isinstance(profile, Mapping):
            return []
        context = contexts_map.get(profile_id)
        name = (context.name if context else None) or profile.get("name", profile_id)
        sensors: list[SensorEntity] = [
            ProfileMetricSensor(coordinator, profile_id, name, PROFILE_SENSOR_DESCRIPTIONS["ppfd"]),
            ProfileMetricSensor(coordinator, profile_id, name, PROFILE_SENSOR_DESCRIPTIONS["dli"]),
        ]
        prof_sensors = profile.get("sensors", {}) if isinstance(profile.get("sensors"), Mapping) else {}
        if prof_sensors.get("temperature") and prof_sensors.get("humidity"):
            sensors.append(ProfileMetricSensor(coordinator, profile_id, name, PROFILE_SENSOR_DESCRIPTIONS["vpd"]))
            sensors.append(ProfileMetricSensor(coordinator, profile_id, name, PROFILE_SENSOR_DESCRIPTIONS["dew_point"]))
            sensors.append(
                ProfileMetricSensor(
                    coordinator,
                    profile_id,
                    name,
                    PROFILE_SENSOR_DESCRIPTIONS["vpd_7d_avg"],
                )
            )
        if prof_sensors.get("moisture"):
            sensors.append(ProfileMetricSensor(coordinator, profile_id, name, PROFILE_SENSOR_DESCRIPTIONS["moisture"]))
            sensors.append(ProfileMetricSensor(coordinator, profile_id, name, PROFILE_SENSOR_DESCRIPTIONS["status"]))
        if profile_registry is not None:
            sensors.extend(
                [
                    ProfileSuccessSensor(coordinator, profile_registry, profile_id, name),
                    ProfileYieldSensor(coordinator, profile_registry, profile_id, name),
                    ProfileEventSensor(coordinator, profile_registry, profile_id, name),
                    ProfileProvenanceSensor(coordinator, profile_registry, profile_id, name),
                    ProfileRunStatusSensor(coordinator, profile_registry, profile_id, name),
                    ProfileFeedingSensor(coordinator, profile_registry, profile_id, name),
                ]
            )
        return sensors

    sensors: list[SensorEntity] = [
        *profile_sensors,
        HortiStatusSensor(coord_ai, coord_local, entry.entry_id, plant_name, plant_id, keep_stale),
        HortiRecommendationSensor(coord_ai, entry.entry_id, plant_name, plant_id, keep_stale),
        EntitlementSummarySensor(entry, plant_name),
    ]

    known_profiles: set[str] = set()
    for context in collection.values():
        context_sensors, metric_pairs = _build_context_sensors(context)
        sensors.extend(context_sensors)
        sensors.extend(sensor for sensor, _ in metric_pairs)
        if context_sensors:
            signatures = known_context_signatures[context.profile_id]
            signatures.update(_sensor_signature(sensor) for sensor in context_sensors)
        if metric_pairs:
            known_metric_keys[context.profile_id].update(signature for _, signature in metric_pairs)
        known_profiles.add(context.profile_id)

    profile_registry = stored.get("profile_registry")
    profiles_map = _profiles_map()
    if profile_coord:
        sensors.append(GardenSummarySensor(profile_coord, entry.entry_id, plant_name))
    if profile_coord and profiles_map:
        for pid in profiles_map:
            sensors.extend(
                _build_profile_option_sensors(
                    profile_coord,
                    profile_registry,
                    contexts,
                    profiles_map,
                    pid,
                )
            )

    cloud_manager = stored.get("cloud_sync_manager")
    if cloud_manager:
        sensors.append(CloudSnapshotAgeSensor(cloud_manager, entry.entry_id, plant_name))
        sensors.append(CloudOutboxSensor(cloud_manager, entry.entry_id, plant_name))
        sensors.append(CloudConnectionSensor(cloud_manager, entry.entry_id, plant_name))

    async_add_entities(sensors, True)

    @callback
    def _handle_profile_update(change: Mapping[str, Iterable[str]] | None) -> None:
        if not isinstance(change, Mapping):
            return
        updated_collection = resolve_profile_context_collection(hass, entry)
        updated_contexts = updated_collection.contexts
        updated_stored = updated_collection.stored
        coordinator = updated_stored.get("coordinator")
        updated_profile_registry = updated_stored.get("profile_registry")
        profiles_map = _profiles_map()

        added = tuple(change.get("added", ()))
        removed = tuple(change.get("removed", ()))
        updated = tuple(change.get("updated", ()))
        if removed:
            for profile_id in removed:
                known_profiles.discard(profile_id)
                known_metric_keys.pop(profile_id, None)
                known_context_signatures.pop(profile_id, None)

        should_refresh = bool(updated)

        new_entities: list[SensorEntity] = []
        for profile_id in added:
            if profile_id in known_profiles:
                continue
            context = updated_contexts.get(profile_id)
            if context is not None:
                context_sensors, metric_pairs = _build_context_sensors(context)
                if context_sensors:
                    signatures = known_context_signatures[profile_id]
                    signatures.update(_sensor_signature(sensor) for sensor in context_sensors)
                    new_entities.extend(context_sensors)
                else:
                    known_context_signatures.setdefault(profile_id, set())
                if metric_pairs:
                    new_entities.extend(sensor for sensor, _ in metric_pairs)
                    known_metric_keys[profile_id].update(signature for _, signature in metric_pairs)
                else:
                    known_metric_keys.setdefault(profile_id, set())
            new_entities.extend(
                _build_profile_option_sensors(
                    coordinator,
                    updated_profile_registry,
                    updated_contexts,
                    profiles_map,
                    profile_id,
                )
            )
            known_profiles.add(profile_id)
            should_refresh = True

        for profile_id in updated:
            context = updated_contexts.get(profile_id)
            if context is None:
                known_metric_keys.pop(profile_id, None)
                known_context_signatures.pop(profile_id, None)
                continue
            context_sensors, metric_pairs = _build_context_sensors(context)
            existing_context_signatures = known_context_signatures.get(profile_id, set())
            new_context_sensors: list[SensorEntity] = []
            for sensor in context_sensors:
                signature = _sensor_signature(sensor)
                if signature in existing_context_signatures:
                    continue
                existing_context_signatures.add(signature)
                new_context_sensors.append(sensor)
            if new_context_sensors:
                known_context_signatures[profile_id] = existing_context_signatures
                new_entities.extend(new_context_sensors)
                should_refresh = True
            elif profile_id not in known_context_signatures:
                known_context_signatures[profile_id] = existing_context_signatures

            current_keys = {signature for _sensor, signature in metric_pairs}
            existing_keys = known_metric_keys.get(profile_id, set())
            new_keys = current_keys - existing_keys
            for sensor, signature in metric_pairs:
                if signature not in new_keys:
                    continue
                new_entities.append(sensor)
            known_metric_keys[profile_id] = current_keys
            should_refresh = should_refresh or bool(new_keys)

        if new_entities:
            async_add_entities(new_entities, True)

        if should_refresh and coordinator is not None:
            refresh = getattr(coordinator, "async_request_refresh", None)
            if callable(refresh):
                result = refresh()
                if inspect.isawaitable(result):
                    hass.async_create_task(result)

    remove = async_dispatcher_connect(
        hass,
        signal_profile_contexts_updated(entry.entry_id),
        _handle_profile_update,
    )
    entry.async_on_unload(remove)


class HortiStatusSensor(
    HorticultureBaseEntity,
    CoordinatorEntity[HortiAICoordinator],
    SensorEntity,
):
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
        CoordinatorEntity.__init__(self, coordinator)
        HorticultureBaseEntity.__init__(
            self,
            entry_id,
            plant_name,
            plant_id,
            model="Plant Profile",
        )
        self._attr_unique_id = self.profile_unique_id(self.entity_description.key)
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


class HortiRecommendationSensor(
    HorticultureBaseEntity,
    CoordinatorEntity[HortiAICoordinator],
    SensorEntity,
):
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
        CoordinatorEntity.__init__(self, coordinator)
        HorticultureBaseEntity.__init__(
            self,
            entry_id,
            plant_name,
            plant_id,
            model="Plant Profile",
        )
        self._attr_unique_id = self.profile_unique_id(self.entity_description.key)
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


class ProfileMetricValueSensor(ProfileContextEntityMixin, HorticultureBaseEntity, SensorEntity):
    """Expose scalar profile metrics such as targets and variables."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_should_poll = False

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        context: ProfileContext,
        category: str,
        key: str,
        meta: Mapping[str, Any],
    ) -> None:
        ProfileContextEntityMixin.__init__(self, hass, entry, context)
        HorticultureBaseEntity.__init__(self, entry.entry_id, context.name, context.profile_id, model="Plant Profile")
        self.hass = hass
        self._entry = entry
        self._category = category
        self._key = key
        self._meta: Mapping[str, Any] = meta
        self._value = meta.get("value") if isinstance(meta, Mapping) else None
        self._attr_available = self._value is not None
        self._attr_unique_id = self.profile_unique_id(f"{category}_{key}")
        label = key.replace("_", " ").title()
        prefix_map = {
            "resolved_targets": "Resolved Target",
            "targets": "Target",
            "variables": "Current",
            "thresholds": "Threshold",
        }
        prefix = prefix_map.get(category, category.replace("_", " ").title())
        self._attr_name = f"{prefix} {label}"
        unit = meta.get("unit") if isinstance(meta, Mapping) else None
        self._attr_native_unit_of_measurement = unit if isinstance(unit, str) else None

        self._update_from_context(context)

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()

    def _refresh_from_context(self) -> None:
        collection = resolve_profile_context_collection(self.hass, self._entry)
        context = collection.contexts.get(self._context_id)
        if context is None:
            self._apply_missing_context()
            self.async_write_ha_state()
            return
        self._update_from_context(context)
        self.async_write_ha_state()

    def _update_from_context(self, context: ProfileContext) -> None:
        meta = context.metric(self._category, self._key) or {}
        self._meta = meta
        self._value = meta.get("value")
        unit = meta.get("unit") if isinstance(meta, Mapping) else None
        self._attr_native_unit_of_measurement = unit if isinstance(unit, str) else None
        self._attr_available = self._value is not None

    def _apply_missing_context(self) -> None:
        self._meta = {}
        self._value = None
        self._attr_native_unit_of_measurement = None
        self._attr_available = False

    def _handle_context_updated(self, context: ProfileContext) -> None:
        super()._handle_context_updated(context)
        self._update_from_context(context)
        if hasattr(self, "async_write_ha_state") and getattr(self, "hass", None):
            self.async_write_ha_state()

    def _handle_context_removed(self) -> None:
        self._apply_missing_context()
        super()._handle_context_removed()

    @property
    def native_value(self):
        return self._value

    @property
    def extra_state_attributes(self):
        meta = self._meta if isinstance(self._meta, Mapping) else {}
        raw = meta.get("raw") if isinstance(meta.get("raw"), Mapping) else None
        attrs: dict[str, Any] = {"category": self._category, "metric_key": self._key}
        if isinstance(raw, Mapping):
            for key, value in raw.items():
                if key in {"value", "target", "current", "current_value"}:
                    continue
                attrs.setdefault(key, value)
        unit = meta.get("unit")
        if isinstance(unit, str):
            attrs.setdefault("unit", unit)
        return attrs


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
        self._attr_unique_id = self.profile_unique_id(description.key)
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
        self._attr_unique_id = self.profile_unique_id("success_rate")
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
        self._attr_unique_id = self.profile_unique_id("yield_total")
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
        self._attr_unique_id = self.profile_unique_id("provenance")
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
        self._attr_unique_id = self.profile_unique_id("run_status")
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
        self._attr_unique_id = self.profile_unique_id("feeding_status")
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
        self._attr_unique_id = self.profile_unique_id("event_activity")
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
