from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator_ai import HortiAICoordinator
from .coordinator_local import HortiLocalCoordinator
from .derived import (
    PlantDLISensor,
    PlantDewPointSensor,
    PlantMoldRiskSensor,
    PlantVPDSensor,
)
from .irrigation_bridge import PlantIrrigationRecommendationSensor
from .utils.entry_helpers import get_entry_data, store_entry_data


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
):
    stored = get_entry_data(hass, entry) or store_entry_data(hass, entry)
    coord_ai: HortiAICoordinator = stored["coordinator_ai"]
    coord_local: HortiLocalCoordinator = stored["coordinator_local"]
    keep_stale: bool = stored.get("keep_stale", True)
    plant_id: str = stored["plant_id"]
    plant_name: str = stored["plant_name"]

    sensors = [
        HortiStatusSensor(coord_ai, coord_local, entry.entry_id, keep_stale),
        HortiRecommendationSensor(coord_ai, entry.entry_id, keep_stale),
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
        sensors.append(
            PlantIrrigationRecommendationSensor(hass, entry, plant_name, plant_id)
        )

    async_add_entities(sensors, True)


class HortiStatusSensor(CoordinatorEntity[HortiAICoordinator], SensorEntity):
    _attr_name = "Horticulture Assistant Status"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_options = ["ok", "error"]

    def __init__(
        self,
        coordinator: HortiAICoordinator,
        local: HortiLocalCoordinator,
        entry_id: str,
        keep_stale: bool,
    ):
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_{entry_id}_status"
        self._local = local
        self._keep_stale = keep_stale
        self._attr_has_entity_name = True

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if self._local:
            self.async_on_remove(
                self._local.async_add_listener(self.async_write_ha_state)
            )

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
        return {
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

    @property
    def available(self) -> bool:
        if self._keep_stale:
            return True
        return super().available

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, "horticulture_assistant")},
            name="Horticulture Assistant",
            manufacturer="Traverse Jurcisin",
        )


class HortiRecommendationSensor(CoordinatorEntity[HortiAICoordinator], SensorEntity):
    _attr_name = "Horticulture Assistant Recommendation"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self, coordinator: HortiAICoordinator, entry_id: str, keep_stale: bool
    ):
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_{entry_id}_recommendation"
        self._keep_stale = keep_stale
        self._attr_has_entity_name = True

    @property
    def native_value(self):
        data = self.coordinator.data or {}
        return data.get("recommendation")

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, "horticulture_assistant")},
            name="Horticulture Assistant",
            manufacturer="Traverse Jurcisin",
        )

    @property
    def available(self) -> bool:
        if self._keep_stale:
            return True
        return super().available
