from __future__ import annotations
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN
from .coordinator import HortiCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    entry_data = hass.data[DOMAIN][entry.entry_id]
    coord: HortiCoordinator = entry_data["coordinator"]
    keep_stale: bool = entry_data.get("keep_stale", True)
    async_add_entities(
        [
            HortiStatusSensor(coord, entry.entry_id, keep_stale),
            HortiRecommendationSensor(coord, entry.entry_id, keep_stale),
        ],
        True,
    )


class HortiStatusSensor(CoordinatorEntity[HortiCoordinator], SensorEntity):
    _attr_name = "Horticulture Assistant Status"

    def __init__(self, coordinator: HortiCoordinator, entry_id: str, keep_stale: bool):
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_{entry_id}_status"
        self._keep_stale = keep_stale
        self._attr_has_entity_name = True

    @property
    def native_value(self):
        data = self.coordinator.data or {}
        return "ok" if data.get("ok") else "error"

    @property
    def extra_state_attributes(self):
        return {
            "last_update_success": self.coordinator.last_update_success,
            "last_exception": str(self.coordinator.last_exception) if self.coordinator.last_exception else None,
            "retry_count": getattr(self.coordinator, "retry_count", 0),
            "breaker_open": getattr(self.coordinator, "breaker_open", False),
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


class HortiRecommendationSensor(CoordinatorEntity[HortiCoordinator], SensorEntity):
    _attr_name = "Horticulture Assistant Recommendation"

    def __init__(self, coordinator: HortiCoordinator, entry_id: str, keep_stale: bool):
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
