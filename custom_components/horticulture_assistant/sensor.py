# File: custom_components/horticulture_assistant/sensor.py
"""Sensor platform for Horticulture Assistant."""
from __future__ import annotations

from datetime import datetime, timedelta
import logging

from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    UnitOfMass,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    UNIT_PERCENT,
    UNIT_MM_DAY,
    CATEGORY_MONITORING,
    CATEGORY_DIAGNOSTIC,
    EVENT_AI_RECOMMENDATION,
    EVENT_YIELD_UPDATE,
    MOVING_AVERAGE_ALPHA,
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

    sensors: list[SensorEntity] = [
        SmoothedMoistureSensor(hass, plant_name, plant_id),
        DailyETSensor(hass, plant_name, plant_id),
        RootZoneDepletionSensor(hass, plant_name, plant_id),
        SmoothedECSensor(hass, plant_name, plant_id),
        EstimatedFieldCapacitySensor(hass, plant_name, plant_id),
        EstimatedWiltingPointSensor(hass, plant_name, plant_id),
        DailyNitrogenAppliedSensor(hass, plant_name, plant_id),
        YieldProgressSensor(hass, plant_name, plant_id),
        AIRecommendationSensor(hass, plant_name, plant_id),
    ]

    async_add_entities(sensors)

class HorticultureBaseSensor(SensorEntity):
    """Base class for horticulture sensors."""
    def __init__(self, hass: HomeAssistant, plant_name: str, plant_id: str):
        self.hass = hass
        self._attr_has_entity_name = True
        self._plant_name = plant_name
        self._plant_id = plant_id

    @property
    def device_info(self) -> dict:
        """Return device information for this sensor."""
        return {
            "identifiers": {(DOMAIN, self._plant_id)},
            "name": self._plant_name,
            "manufacturer": "Horticulture Assistant",
            "model": "AI Monitored Plant",
        }

    def _get_state_value(self, entity_id: str) -> float | None:
        """Get state of an entity as a float, or None if unavailable/invalid."""
        state = self.hass.states.get(entity_id)
        if not state or state.state in ("unknown", "unavailable"):
            return None
        try:
            return float(state.state)
        except (ValueError, TypeError):
            _LOGGER.warning("State of %s is not a number: %s", entity_id, state.state)
            return None

class ExponentialMovingAverageSensor(HorticultureBaseSensor):
    """Base sensor applying an exponential moving average to another sensor."""

    def __init__(
        self,
        hass: HomeAssistant,
        plant_name: str,
        plant_id: str,
        *,
        source_sensor: str,
        name: str,
        unique_id: str,
        unit: str,
        icon: str,
        precision: int,
        device_class: SensorDeviceClass | None = None,
    ) -> None:
        super().__init__(hass, plant_name, plant_id)
        self._source = source_sensor
        self._precision = precision
        self._attr_name = name
        self._attr_unique_id = unique_id
        self._attr_native_unit_of_measurement = unit
        self._attr_icon = icon
        self._attr_device_class = device_class
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_entity_category = CATEGORY_MONITORING

    async def async_update(self) -> None:
        """Apply the EMA calculation to the configured source sensor."""
        raw_val = self._get_state_value(self._source)
        if raw_val is None:
            _LOGGER.debug("EMA source not available: %s", self._source)
            self._attr_native_value = None
            return

        if not hasattr(self, "_ema"):
            self._ema = raw_val
        else:
            self._ema = (
                MOVING_AVERAGE_ALPHA * raw_val
                + (1 - MOVING_AVERAGE_ALPHA) * self._ema
            )

        self._attr_native_value = round(self._ema, self._precision)


class SmoothedMoistureSensor(ExponentialMovingAverageSensor):
    """Smoothed moisture using an exponential moving average."""

    def __init__(self, hass: HomeAssistant, plant_name: str, plant_id: str):
        super().__init__(
            hass,
            plant_name,
            plant_id,
            source_sensor=f"sensor.{plant_id}_raw_moisture",
            name="Smoothed Moisture",
            unique_id=f"{plant_id}_smoothed_moisture",
            unit=UNIT_PERCENT,
            icon="mdi:water-percent",
            precision=1,
            device_class=SensorDeviceClass.MOISTURE,
        )

class DailyETSensor(HorticultureBaseSensor):
    """Sensor estimating daily ET (Evapotranspiration) loss."""
    def __init__(self, hass: HomeAssistant, plant_name: str, plant_id: str):
        super().__init__(hass, plant_name, plant_id)
        self._attr_name = "Estimated Daily ET"
        self._attr_unique_id = f"{plant_id}_daily_et"
        self._attr_native_unit_of_measurement = UNIT_MM_DAY
        self._attr_device_class = SensorDeviceClass.PRECIPITATION
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:weather-sunny"
        self._attr_entity_category = CATEGORY_MONITORING

    async def async_update(self):
        """Calculate daily ET estimate (using a simple temperature/humidity formula)."""
        temp = self._get_state_value(f"sensor.{self._plant_id}_raw_temperature")
        hum = self._get_state_value(f"sensor.{self._plant_id}_raw_humidity")
        if temp is not None and hum is not None:
            et = max(0, (temp - 10) * (1 - hum / 100) * 0.5)
            self._attr_native_value = round(et, 1)
        else:
            _LOGGER.debug("Temp or humidity not available for ET calc, using default")
            # Fallback stub
            self._attr_native_value = 4.5

class RootZoneDepletionSensor(HorticultureBaseSensor):
    """Sensor estimating % root zone water depletion."""
    def __init__(self, hass: HomeAssistant, plant_name: str, plant_id: str):
        super().__init__(hass, plant_name, plant_id)
        self._attr_name = "Root Zone Depletion"
        self._attr_unique_id = f"{plant_id}_depletion"
        self._attr_native_unit_of_measurement = UNIT_PERCENT
        self._attr_device_class = SensorDeviceClass.MOISTURE
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:tree-outline"
        self._attr_entity_category = CATEGORY_MONITORING

    async def async_update(self):
        """Estimate root zone depletion based on moisture, field capacity, and wilting point."""
        current = self._get_state_value(f"sensor.{self._plant_id}_smoothed_moisture")
        fc = self._get_state_value(f"sensor.{self._plant_id}_field_capacity")
        wp = self._get_state_value(f"sensor.{self._plant_id}_wilting_point")
        if current is None:
            _LOGGER.debug("Smoothed moisture not available for depletion: %s", self._plant_id)
            self._attr_native_value = None
            return
        # If field capacity and wilting point known, use proportional depletion
        if fc is not None and wp is not None and fc > wp:
            depletion = (fc - current) / (fc - wp) * 100
            self._attr_native_value = round(max(0, min(depletion, 100)), 1)
        else:
            _LOGGER.debug("Using fallback depletion calculation for: %s", self._plant_id)
            self._attr_native_value = round(max(0, min(100 - current, 100)), 1)

class SmoothedECSensor(ExponentialMovingAverageSensor):
    """Smoothed EC reading using an exponential moving average."""

    def __init__(self, hass: HomeAssistant, plant_name: str, plant_id: str):
        super().__init__(
            hass,
            plant_name,
            plant_id,
            source_sensor=f"sensor.{plant_id}_raw_ec",
            name="Smoothed EC",
            unique_id=f"{plant_id}_smoothed_ec",
            unit="mS/cm",
            icon="mdi:water-outline",
            precision=2,
        )

class EstimatedFieldCapacitySensor(HorticultureBaseSensor):
    """Estimate of field capacity from past max moisture post-irrigation."""
    def __init__(self, hass: HomeAssistant, plant_name: str, plant_id: str):
        super().__init__(hass, plant_name, plant_id)
        self._attr_name = "Estimated Field Capacity"
        self._attr_unique_id = f"{plant_id}_field_capacity"
        self._attr_native_unit_of_measurement = UNIT_PERCENT
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:water"
        self._attr_entity_category = CATEGORY_DIAGNOSTIC

    async def async_update(self):
        """Estimate field capacity (peak moisture over recent period)."""
        _LOGGER.debug("Estimating field capacity for plant: %s", self._plant_id)
        current = self._get_state_value(f"sensor.{self._plant_id}_raw_moisture")
        if current is not None:
            max_val = getattr(self, "_max_moisture", None)
            self._max_moisture = current if max_val is None else max(max_val, current)
            self._attr_native_value = self._max_moisture
        else:
            self._attr_native_value = getattr(self, "_max_moisture", None)

class EstimatedWiltingPointSensor(HorticultureBaseSensor):
    """Estimate of permanent wilting point based on dry-down observation."""
    def __init__(self, hass: HomeAssistant, plant_name: str, plant_id: str):
        super().__init__(hass, plant_name, plant_id)
        self._attr_name = "Estimated Wilting Point"
        self._attr_unique_id = f"{plant_id}_wilting_point"
        self._attr_native_unit_of_measurement = UNIT_PERCENT
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:water-off"
        self._attr_entity_category = CATEGORY_DIAGNOSTIC

    async def async_update(self):
        """Estimate wilting point (minimum moisture over recent period)."""
        _LOGGER.debug("Estimating wilting point for plant: %s", self._plant_id)
        current = self._get_state_value(f"sensor.{self._plant_id}_raw_moisture")
        if current is not None:
            min_val = getattr(self, "_min_moisture", None)
            self._min_moisture = current if min_val is None else min(min_val, current)
            self._attr_native_value = self._min_moisture
        else:
            self._attr_native_value = getattr(self, "_min_moisture", None)

class DailyNitrogenAppliedSensor(HorticultureBaseSensor):
    """Amount of nitrogen applied to plant today."""
    def __init__(self, hass: HomeAssistant, plant_name: str, plant_id: str):
        super().__init__(hass, plant_name, plant_id)
        self._attr_name = "Nitrogen Applied Today"
        self._attr_unique_id = f"{plant_id}_daily_nitrogen"
        self._attr_native_unit_of_measurement = UnitOfMass.MILLIGRAMS
        self._attr_icon = "mdi:chemical-weapon"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_entity_category = CATEGORY_MONITORING

    async def async_update(self):
        """Calculate daily nitrogen applied."""
        _LOGGER.debug("Calculating daily nitrogen for plant: %s", self._plant_id)
        tracker = self.hass.data.get(DOMAIN, {}).get("nutrient_tracker")
        if tracker is None:
            self._attr_native_value = None
            return

        today = datetime.now()
        summary = tracker.summarize_mg_for_day(today, self._plant_id)
        self._attr_native_value = round(summary.get("N", 0.0), 2)

class YieldProgressSensor(HorticultureBaseSensor):
    """Yield or growth progress (user updated or AI projected)."""
    def __init__(self, hass: HomeAssistant, plant_name: str, plant_id: str):
        super().__init__(hass, plant_name, plant_id)
        self._attr_name = "Yield Progress"
        self._attr_unique_id = f"{plant_id}_yield"
        self._attr_native_unit_of_measurement = UnitOfMass.GRAMS
        self._attr_device_class = SensorDeviceClass.WEIGHT
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:chart-line"
        self._attr_entity_category = CATEGORY_MONITORING

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        self._yield_value = None
        self.hass.bus.async_listen(EVENT_YIELD_UPDATE, self._handle_event)

    def _handle_event(self, event):
        if event.data.get("plant_id") == self._plant_id:
            # Expect event data key "yield"
            self._yield_value = event.data.get("yield", 0)

    async def async_update(self):
        """Update yield progress from last event."""
        # Use the latest received yield value
        self._attr_native_value = getattr(self, "_yield_value", None)

class AIRecommendationSensor(HorticultureBaseSensor):
    """AI-generated recommendation (string message)."""
    def __init__(self, hass: HomeAssistant, plant_name: str, plant_id: str):
        super().__init__(hass, plant_name, plant_id)
        self._attr_name = "AI Recommendation"
        self._attr_unique_id = f"{plant_id}_ai_recommendation"
        self._attr_icon = "mdi:robot-outline"
        self._attr_entity_category = CATEGORY_DIAGNOSTIC
        # No unit or device class for free-text message

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        self._recommendation = "No suggestions."
        self.hass.bus.async_listen(EVENT_AI_RECOMMENDATION, self._handle_event)

    def _handle_event(self, event):
        if event.data.get("plant_id") == self._plant_id:
            self._recommendation = event.data.get("recommendation", "")

    async def async_update(self):
        """Update AI recommendation from last event."""
        self._attr_native_value = getattr(self, "_recommendation", "No suggestions.")