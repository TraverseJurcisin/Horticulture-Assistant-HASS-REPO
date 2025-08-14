from __future__ import annotations
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN
from .coordinator_ai import HortiAICoordinator
from .coordinator_local import HortiLocalCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    entry_data = hass.data[DOMAIN][entry.entry_id]
    coord_ai: HortiAICoordinator = entry_data["coordinator_ai"]
    coord_local: HortiLocalCoordinator = entry_data["coordinator_local"]
    keep_stale: bool = entry_data.get("keep_stale", True)
    async_add_entities(
        [
            HortiStatusSensor(coord_ai, coord_local, entry.entry_id, keep_stale),
            HortiRecommendationSensor(coord_ai, entry.entry_id, keep_stale),
        ],
        True,
    )


class HortiStatusSensor(CoordinatorEntity[HortiAICoordinator], SensorEntity):
    _attr_name = "Horticulture Assistant Status"

    def __init__(self, coordinator: HortiAICoordinator, local: HortiLocalCoordinator, entry_id: str, keep_stale: bool):
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_{entry_id}_status"
        self._local = local
        self._keep_stale = keep_stale
        self._attr_has_entity_name = True

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if self._local:
            self.async_on_remove(self._local.async_add_listener(self.async_write_ha_state))

    @property
    def native_value(self):
        if not self.coordinator.last_update_success:
            return "error"
        data = self.coordinator.data or {}
        return "ok" if data.get("ok") is True else "error"

    @property
    def extra_state_attributes(self):
        attrs = {
            "last_update_success": self.coordinator.last_update_success,
            "last_exception": str(self.coordinator.last_exception)
            if self.coordinator.last_exception
            else None,
        }
        api = self.coordinator.__dict__.get("api") or getattr(self.coordinator, "api", None)
        if api:
            attrs["retry_count"] = max(
                getattr(api, "_failures", 0),
                getattr(self.coordinator, "retry_count", 0),
            )
            attrs["breaker_open"] = getattr(api, "_open", None) is False
            attrs["latency_ms"] = getattr(
                api, "last_latency_ms", getattr(self.coordinator, "latency_ms", None)
            )
        else:
            attrs["retry_count"] = getattr(self.coordinator, "retry_count", None)
            attrs["breaker_open"] = getattr(self.coordinator, "breaker_open", None)
            attrs["latency_ms"] = getattr(self.coordinator, "latency_ms", None)
        return attrs

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

    def __init__(self, coordinator: HortiAICoordinator, entry_id: str, keep_stale: bool):
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
