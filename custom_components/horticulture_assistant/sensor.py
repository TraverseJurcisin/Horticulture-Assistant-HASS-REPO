"""Sensor platform for Horticulture Assistant."""
from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    UnitOfTemperature,
    UnitOfVolume,
    UnitOfMass,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    UNIT_PERCENT,
    UNIT_MM_DAY,
    SENSOR_TYPE_MOISTURE,
    SENSOR_TYPE_ET,
    SENSOR_TYPE_VWC,
    SENSOR_TYPE_EC,
    CATEGORY_MONITORING,
    CATEGORY_DIAGNOSTIC,
    EVENT_AI_RECOMMENDATION,
    TAG_CULTIVAR,
)

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=5)  # fallback update rate


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up horticulture assistant sensors from a config entry."""
    _LOGGER.debug("Setting up horticulture_assistant sensors")

    plant_id = entry.entry_id
    plant_name = f"Plant {plant_id[:6]}"

    sensors = [
        SmoothedMoistureSensor(hass, plant_name, plant_id),
        DailyETSensor(hass, plant_name, plant_id),
        RootZoneDepletionSensor(hass, plant_name, plant_id),
    ]

    async_add_entities(sensors)


class HorticultureBaseSensor(SensorEntity):
    """Base class for horticulture sensors."""

    def __init__(self, hass, plant_name, plant_id):
        self.hass = hass
        self._attr_has_entity_name = True
        self._plant_name = plant_name
        self._plant_id = plant_id

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._plant_id)},
            "name": self._plant_name,
            "manufacturer": "Horticulture Assistant",
            "model": "AI Monitored Plant",
        }


class SmoothedMoistureSensor(HorticultureBaseSensor):
    """Smoothed moisture value for plant using rolling average."""

    def __init__(self, hass, plant_name, plant_id):
        super().__init__(hass, plant_name, plant_id)
        self._attr_name = "Smoothed Moisture"
        self._attr_unique_id = f"{plant_id}_smoothed_moisture"
        self._attr_native_unit_of_measurement = UNIT_PERCENT
        self._attr_state_class = "measurement"
        self._attr_device_class = "moisture"
        self._attr_icon = "mdi:water-percent"

    async def async_update(self):
        """Update with smoothed data."""
        raw_entity_id = f"sensor.{self._plant_id}_raw_moisture"
        try:
            history = self.hass.states.get(raw_entity_id)
            if history:
                # Simple stub logic for now, to be replaced with actual smoothing
                self._attr_native_value = float(history.state)
        except Exception as e:
            _LOGGER.warning("Could not update smoothed moisture: %s", e)
            self._attr_native_value = None


class DailyETSensor(HorticultureBaseSensor):
    """Sensor estimating daily ET (Evapotranspiration) loss."""

    def __init__(self, hass, plant_name, plant_id):
        super().__init__(hass, plant_name, plant_id)
        self._attr_name = "Estimated Daily ET"
        self._attr_unique_id = f"{plant_id}_daily_et"
        self._attr_native_unit_of_measurement = UNIT_MM_DAY
        self._attr_device_class = "precipitation"
        self._attr_icon = "mdi:weather-sunny"

    async def async_update(self):
        """Calculate daily ET estimate (placeholder for now)."""
        # Placeholder: Replace with dynamic ET algorithm later
        self._attr_native_value = 4.5  # mm/day stub


class RootZoneDepletionSensor(HorticultureBaseSensor):
    """Sensor estimating % root zone water depletion."""

    def __init__(self, hass, plant_name, plant_id):
        super().__init__(hass, plant_name, plant_id)
        self._attr_name = "Root Zone Depletion"
        self._attr_unique_id = f"{plant_id}_depletion"
        self._attr_native_unit_of_measurement = UNIT_PERCENT
        self._attr_device_class = "moisture"
        self._attr_icon = "mdi:tree-outline"

    async def async_update(self):
        """Estimate depletion based on smoothed moisture."""
        moisture_sensor_id = f"sensor.{self._plant_id}_smoothed_moisture"
        smoothed = self.hass.states.get(moisture_sensor_id)
        if smoothed and smoothed.state not in ("unknown", "unavailable"):
            try:
                val = float(smoothed.state)
                depletion = 100 - val  # Stub logic
                self._attr_native_value = max(0, min(depletion, 100))
            except ValueError:
                self._attr_native_value = None

class SmoothedECSensor(HorticultureBaseSensor):
    """Smoothed electrical conductivity value using rolling average."""

    def __init__(self, hass, plant_name, plant_id):
        super().__init__(hass, plant_name, plant_id)
        self._attr_name = "Smoothed EC"
        self._attr_unique_id = f"{plant_id}_smoothed_ec"
        self._attr_native_unit_of_measurement = "mS/cm"
        self._attr_icon = "mdi:water-outline"
        self._attr_state_class = "measurement"

    async def async_update(self):
        try:
            raw = self.hass.states.get(f"sensor.{self._plant_id}_raw_ec")
            self._attr_native_value = float(raw.state) if raw else None
        except:
            self._attr_native_value = None


class EstimatedFieldCapacitySensor(HorticultureBaseSensor):
    """Estimate of field capacity from past max moisture post-irrigation."""

    def __init__(self, hass, plant_name, plant_id):
        super().__init__(hass, plant_name, plant_id)
        self._attr_name = "Estimated Field Capacity"
        self._attr_unique_id = f"{plant_id}_field_capacity"
        self._attr_native_unit_of_measurement = UNIT_PERCENT
        self._attr_icon = "mdi:water"
        self._attr_state_class = "measurement"

    async def async_update(self):
        # Placeholder: Track peak % moisture in last 3 days
        self._attr_native_value = 60  # Stub: replace with historical Influx query


class EstimatedWiltingPointSensor(HorticultureBaseSensor):
    """Estimate of permanent wilting point based on dry-down observation."""

    def __init__(self, hass, plant_name, plant_id):
        super().__init__(hass, plant_name, plant_id)
        self._attr_name = "Estimated Wilting Point"
        self._attr_unique_id = f"{plant_id}_wilting_point"
        self._attr_native_unit_of_measurement = UNIT_PERCENT
        self._attr_icon = "mdi:water-off"
        self._attr_state_class = "measurement"

    async def async_update(self):
        # Placeholder: Use observed dry minimum over time
        self._attr_native_value = 15  # Stub


class DailyNitrogenAppliedSensor(HorticultureBaseSensor):
    """Amount of nitrogen applied to plant today."""

    def __init__(self, hass, plant_name, plant_id):
        super().__init__(hass, plant_name, plant_id)
        self._attr_name = "Nitrogen Applied Today"
        self._attr_unique_id = f"{plant_id}_daily_nitrogen"
        self._attr_native_unit_of_measurement = "mg"
        self._attr_icon = "mdi:chemical-weapon"
        self._attr_state_class = "total"

    async def async_update(self):
        # Placeholder: Use fertigation tracking logic later
        self._attr_native_value = 32  # Stub


class YieldProgressSensor(HorticultureBaseSensor):
    """Yield or growth progress (user updated or AI projected)."""

    def __init__(self, hass, plant_name, plant_id):
        super().__init__(hass, plant_name, plant_id)
        self._attr_name = "Yield Progress"
        self._attr_unique_id = f"{plant_id}_yield"
        self._attr_native_unit_of_measurement = UNIT_GRAMS
        self._attr_icon = "mdi:chart-line"
        self._attr_state_class = "measurement"

    async def async_update(self):
        # Placeholder: Replace with user entry or AI yield model
        self._attr_native_value = 120  # Stub (e.g. grams of fruit)


class AIRecommendationSensor(HorticultureBaseSensor):
    """AI-generated recommendation (shown as string message)."""

    def __init__(self, hass, plant_name, plant_id):
        super().__init__(hass, plant_name, plant_id)
        self._attr_name = "AI Recommendation"
        self._attr_unique_id = f"{plant_id}_ai_recommendation"
        self._attr_icon = "mdi:robot-outline"
        self._attr_native_unit_of_measurement = None
        self._attr_device_class = None

    async def async_update(self):
        # Later filled in via event or script
        msg_entity = self.hass.states.get(f"sensor.{self._plant_id}_ai_message")
        self._attr_native_value = msg_entity.state if msg_entity else "No suggestions."