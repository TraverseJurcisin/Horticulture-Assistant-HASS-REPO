"""Binary sensor platform for Horticulture Assistant."""

from __future__ import annotations

import logging
from collections.abc import Iterable, Mapping

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CATEGORY_CONTROL, CATEGORY_DIAGNOSTIC, DOMAIN, signal_profile_contexts_updated
from .entity_base import HorticultureBaseEntity, HorticultureEntryEntity
from .entity_utils import ensure_entities_exist
from .profile_monitor import ProfileMonitor
from .utils.entry_helpers import ProfileContext, resolve_profile_context_collection

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up horticulture assistant binary sensors from a config entry."""
    _LOGGER.debug("Setting up horticulture_assistant binary sensors")
    collection = resolve_profile_context_collection(hass, entry)
    stored = collection.stored

    known_profiles: set[str] = set()

    def _build_context_entities(context: ProfileContext) -> list[BinarySensorEntity]:
        profile_id = context.profile_id
        plant_name = context.name
        ensure_entities_exist(
            hass,
            profile_id,
            list(
                context.sensor_ids_for_roles(
                    "moisture",
                    "temperature",
                    "humidity",
                    "ec",
                    "co2",
                )
            ),
            placeholders={"plant_id": profile_id, "profile_name": plant_name},
        )
        return [
            SensorHealthBinarySensor(
                hass,
                entry.entry_id,
                context,
            ),
            IrrigationReadinessBinarySensor(
                hass,
                entry.entry_id,
                context,
            ),
            FaultDetectionBinarySensor(
                hass,
                entry.entry_id,
                context,
            ),
        ]

    sensors: list[BinarySensorEntity] = []
    for context in collection.values():
        sensors.extend(_build_context_entities(context))
        known_profiles.add(context.profile_id)

    manager = stored.get("cloud_sync_manager")
    if manager:
        entry_name = stored.get("plant_name")
        sensors.append(CloudConnectionBinarySensor(manager, entry.entry_id, entry_name))
        sensors.append(LocalOnlyModeBinarySensor(manager, entry.entry_id, entry_name))

    async_add_entities(sensors, True)

    @callback
    def _handle_profile_update(change: Mapping[str, Iterable[str]] | None) -> None:
        if not isinstance(change, Mapping):
            return
        added = tuple(change.get("added", ()))
        if not added:
            return

        updated_collection = resolve_profile_context_collection(hass, entry)
        new_entities: list[BinarySensorEntity] = []
        for profile_id in added:
            if profile_id in known_profiles:
                continue
            context = updated_collection.contexts.get(profile_id)
            if context is None:
                continue
            new_entities.extend(_build_context_entities(context))
            known_profiles.add(profile_id)

        if new_entities:
            async_add_entities(new_entities, True)

    remove = async_dispatcher_connect(
        hass,
        signal_profile_contexts_updated(entry.entry_id),
        _handle_profile_update,
    )
    entry.async_on_unload(remove)


class HorticultureBaseBinarySensor(HorticultureBaseEntity, BinarySensorEntity):
    """Base class for horticulture binary sensors."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry_id: str,
        context: ProfileContext,
    ) -> None:
        super().__init__(entry_id, context.name, context.profile_id, model="AI Monitored Plant")
        self.hass = hass
        self._entry_id = entry_id
        self._context = context
        self._sensor_map = {role: list(ids) for role, ids in context.sensors.items() if ids}
        self._monitor = ProfileMonitor(hass, context)


class SensorHealthBinarySensor(HorticultureBaseBinarySensor):
    """Binary sensor to indicate overall sensor health (any raw sensor offline)."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry_id: str,
        context: ProfileContext,
    ):
        super().__init__(hass, entry_id, context)
        self._attr_name = "Sensor Health"
        self._attr_unique_id = f"{context.profile_id}_sensor_health"
        self._attr_device_class = BinarySensorDeviceClass.PROBLEM
        self._attr_icon = "mdi:heart-pulse"
        self._attr_entity_category = CATEGORY_DIAGNOSTIC

    async def async_update(self):
        """Check if raw sensors are online (no missing or unavailable sensors)."""

        result = self._monitor.evaluate()
        attention = result.issues_for("attention")
        self._attr_is_on = bool(attention)
        self._attr_available = bool(result.sensors)
        self._attr_extra_state_attributes = result.as_attributes(severities=("attention",))


class IrrigationReadinessBinarySensor(HorticultureBaseBinarySensor):
    """Binary sensor to indicate if irrigation should run (root zone dry)."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry_id: str,
        context: ProfileContext,
    ):
        super().__init__(hass, entry_id, context)
        self._attr_name = "Irrigation Readiness"
        self._attr_unique_id = f"{context.profile_id}_irrigation_readiness"
        self._attr_device_class = BinarySensorDeviceClass.MOISTURE
        self._attr_icon = "mdi:water-alert"
        self._attr_entity_category = CATEGORY_CONTROL
        self._threshold = 30.0

    async def async_update(self):
        """Determine if root zone is dry enough for watering."""

        moisture_id = self._context.first_sensor("moisture") or self._context.first_sensor("soil_moisture")
        if not moisture_id:
            self._attr_is_on = False
            self._attr_extra_state_attributes = {
                "reason": "no_moisture_sensor",
                "threshold": self._threshold,
            }
            return

        state = self.hass.states.get(moisture_id)
        if not state or state.state in ("unknown", "unavailable"):
            _LOGGER.debug("Moisture sensor unavailable for irrigation readiness: %s", moisture_id)
            self._attr_is_on = False
            self._attr_extra_state_attributes = {
                "reason": "sensor_unavailable",
                "sensor": moisture_id,
                "threshold": self._threshold,
            }
            return

        try:
            moisture = float(state.state)
        except (ValueError, TypeError):
            _LOGGER.error("Invalid moisture value for irrigation readiness: %s", state.state)
            self._attr_is_on = False
            self._attr_extra_state_attributes = {
                "reason": "invalid_state",
                "sensor": moisture_id,
                "value": state.state,
                "threshold": self._threshold,
            }
            return

        threshold = (
            self._context.get_threshold("moisture_min")
            or self._context.get_threshold("soil_moisture_min")
            or self._threshold
        )
        try:
            threshold_value = float(threshold)
        except (TypeError, ValueError):
            threshold_value = self._threshold

        self._attr_is_on = moisture <= threshold_value
        self._attr_extra_state_attributes = {
            "sensor": moisture_id,
            "moisture": moisture,
            "threshold": threshold_value,
        }


class FaultDetectionBinarySensor(HorticultureBaseBinarySensor):
    """Binary sensor to detect faults (sensor out of bounds or removed)."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry_id: str,
        context: ProfileContext,
    ):
        super().__init__(hass, entry_id, context)
        self._attr_name = "Fault Detection"
        self._attr_unique_id = f"{context.profile_id}_fault_detection"
        self._attr_device_class = BinarySensorDeviceClass.SAFETY
        self._attr_icon = "mdi:alert"
        self._attr_entity_category = CATEGORY_DIAGNOSTIC

    async def async_update(self):
        """Check for sensor faults or out-of-range values."""

        result = self._monitor.evaluate()
        problems = result.issues_for("problem")
        self._attr_is_on = bool(problems)
        self._attr_available = bool(result.sensors)
        self._attr_extra_state_attributes = result.as_attributes(severities=("problem",))


class CloudSyncBinarySensor(HorticultureEntryEntity, BinarySensorEntity):
    """Base class for cloud sync diagnostic binary sensors."""

    _attr_entity_category = CATEGORY_DIAGNOSTIC
    _attr_should_poll = True

    def __init__(self, manager, entry_id: str, plant_name: str) -> None:
        HorticultureEntryEntity.__init__(self, entry_id, default_device_name=plant_name)
        self._manager = manager
        self._entry_id = entry_id

    def _cloud_status(self) -> tuple[dict, dict, bool]:  # type: ignore[override]
        status = self._manager.status()
        connection = status.get("connection") or {}
        configured = bool(connection.get("configured", status.get("configured")))
        self._attr_available = configured
        return status, connection, configured


class CloudConnectionBinarySensor(CloudSyncBinarySensor):
    """Indicate whether the edge is connected to the cloud service."""

    def __init__(self, manager, entry_id: str, plant_name: str) -> None:
        super().__init__(manager, entry_id, plant_name)
        self._attr_name = "Cloud Connected"
        self._attr_unique_id = f"{DOMAIN}_{entry_id}_cloud_connected"
        self._attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
        self._attr_icon = "mdi:cloud-check"

    async def async_update(self) -> None:
        status, connection, _configured = self._cloud_status()
        self._attr_is_on = bool(connection.get("connected"))
        self._attr_extra_state_attributes = {
            "reason": connection.get("reason"),
            "last_success_at": connection.get("last_success_at") or status.get("last_success_at"),
            "last_success_age_seconds": connection.get("last_success_age_seconds"),
            "cloud_snapshot_age_days": status.get("cloud_snapshot_age_days"),
            "outbox_size": status.get("outbox_size"),
            "cloud_cache_entries": status.get("cloud_cache_entries"),
            "last_pull_error": status.get("last_pull_error"),
            "last_push_error": status.get("last_push_error"),
        }


class LocalOnlyModeBinarySensor(CloudSyncBinarySensor):
    """Signal when the integration is operating in offline-only mode."""

    def __init__(self, manager, entry_id: str, plant_name: str) -> None:
        super().__init__(manager, entry_id, plant_name)
        self._attr_name = "Local Only Mode"
        self._attr_unique_id = f"{DOMAIN}_{entry_id}_local_only"
        self._attr_device_class = BinarySensorDeviceClass.PROBLEM
        self._attr_icon = "mdi:home-off"

    async def async_update(self) -> None:
        status, connection, _configured = self._cloud_status()
        local_only = connection.get("local_only")
        if local_only is None:
            local_only = not bool(connection.get("connected"))
        self._attr_is_on = bool(local_only)
        self._attr_extra_state_attributes = {
            "reason": connection.get("reason"),
            "connected": connection.get("connected"),
            "last_success_at": connection.get("last_success_at") or status.get("last_success_at"),
            "last_success_age_seconds": connection.get("last_success_age_seconds"),
            "cloud_snapshot_age_days": status.get("cloud_snapshot_age_days"),
            "outbox_size": status.get("outbox_size"),
            "cloud_cache_entries": status.get("cloud_cache_entries"),
            "last_pull_error": status.get("last_pull_error"),
            "last_push_error": status.get("last_push_error"),
        }
