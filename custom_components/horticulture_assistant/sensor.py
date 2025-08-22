from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
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
    PlantVPDSensor,
)
from .entity import HorticultureBaseEntity
from .irrigation_bridge import PlantIrrigationRecommendationSensor
from .utils.entry_helpers import get_entry_data, store_entry_data


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
):
    stored = get_entry_data(hass, entry) or store_entry_data(hass, entry)
    coord_ai: HortiAICoordinator = stored["coordinator_ai"]
    coord_local: HortiLocalCoordinator = stored["coordinator_local"]
    profile_coord: HorticultureCoordinator | None = stored.get("coordinator")
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

    profiles = entry.options.get(CONF_PROFILES, {})
    if profile_coord and profiles:
        for pid, profile in profiles.items():
            name = profile.get("name", pid)
            sensors.append(ProfileDLISensor(profile_coord, pid, name))

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
        self._citations: dict | None = None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if self._local:
            self.async_on_remove(
                self._local.async_add_listener(self.async_write_ha_state)
            )
        # Load citation summary once on startup
        from .profile.store import async_load_all

        profiles = await async_load_all(self.hass)
        total = 0
        summary: dict[str, int] = {}
        links: list[str] = []
        link_set: set[str] = set()
        for prof in profiles.values():
            for key, data in (prof.get("variables") or {}).items():
                cits = data.get("citations") or []
                if not cits:
                    continue
                total += len(cits)
                summary[key] = summary.get(key, 0) + len(cits)
                for cit in cits:
                    if len(links) >= 3:
                        break
                    url = cit.get("url")
                    if url and url not in link_set:
                        links.append(url)
                        link_set.add(url)
        self._citations = {
            "citations_count": total,
            "citations_summary": summary,
            "citations_links_preview": links,
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


class ProfileDLISensor(HorticultureBaseEntity, SensorEntity):
    """DLI sensor backed by the profile coordinator."""

    _attr_native_unit_of_measurement = "mol/m²·day"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:weather-sunny-alert"

    def __init__(
        self, coordinator: HorticultureCoordinator, profile_id: str, profile_name: str
    ) -> None:
        super().__init__(coordinator, profile_id, profile_name)
        self._attr_unique_id = f"{profile_id}:dli"
        self._attr_name = "Daily Light Integral"

    @property
    def native_value(self):
        return (
            (self.coordinator.data or {})
            .get("profiles", {})
            .get(self._profile_id, {})
            .get("metrics", {})
            .get("dli")
        )
