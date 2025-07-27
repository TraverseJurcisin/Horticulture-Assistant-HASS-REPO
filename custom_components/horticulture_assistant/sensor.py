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

from .utils.state_helpers import aggregate_sensor_values
from .utils.sensor_map import build_sensor_map
from .utils.entry_helpers import get_entry_data, store_entry_data

from plant_engine.environment_manager import (
    score_environment,
    classify_environment_quality,
)
from .utils.plant_registry import get_plant_type

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
from .entity_base import HorticultureBaseEntity

_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = timedelta(minutes=5)  # fallback update rate

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up horticulture assistant sensors from a config entry."""
    _LOGGER.debug("Setting up horticulture_assistant sensors")
    stored = get_entry_data(hass, entry) or store_entry_data(hass, entry)
    plant_id = stored["plant_id"]
    plant_name = stored["plant_name"]

    sensor_map = build_sensor_map(
        entry.data,
        plant_id,
        keys=(
            "moisture_sensors",
            "temperature_sensors",
            "humidity_sensors",
            "light_sensors",
            "ec_sensors",
            "co2_sensors",
        ),
    )

    sensors: list[SensorEntity] = [
        SmoothedMoistureSensor(hass, plant_name, plant_id, sensor_map),
        DailyETSensor(hass, plant_name, plant_id, sensor_map),
        RootZoneDepletionSensor(hass, plant_name, plant_id, sensor_map),
        SmoothedECSensor(hass, plant_name, plant_id, sensor_map),
        EstimatedFieldCapacitySensor(hass, plant_name, plant_id, sensor_map),
        EstimatedWiltingPointSensor(hass, plant_name, plant_id, sensor_map),
        DailyNitrogenAppliedSensor(hass, plant_name, plant_id, sensor_map),
        YieldProgressSensor(hass, plant_name, plant_id, sensor_map),
        AIRecommendationSensor(hass, plant_name, plant_id, sensor_map),
        EnvironmentScoreSensor(hass, plant_name, plant_id, sensor_map),
        EnvironmentQualitySensor(hass, plant_name, plant_id, sensor_map),
    ]

    async_add_entities(sensors)

class HorticultureBaseSensor(HorticultureBaseEntity, SensorEntity):
    """Base class for horticulture sensors."""

    def __init__(
        self,
        hass: HomeAssistant,
        plant_name: str,
        plant_id: str,
        sensor_map: dict[str, list[str]] | None = None,
    ) -> None:
        super().__init__(plant_name, plant_id, model="AI Monitored Plant")
        self.hass = hass
        if sensor_map is None:
            sensor_map = build_sensor_map({}, plant_id)
        self._sensor_map = sensor_map

    def _get_state_value(self, entity_id: str | list[str] | None) -> float | None:
        """Return numeric state or aggregated value of ``entity_id``(s)."""
        if not entity_id:
            return None
        return aggregate_sensor_values(self.hass, entity_id)

class ExponentialMovingAverageSensor(HorticultureBaseSensor):
    """Base sensor applying an exponential moving average to another sensor."""

    def __init__(
        self,
        hass: HomeAssistant,
        plant_name: str,
        plant_id: str,
        *,
        source_sensor: str | list[str],
        name: str,
        unique_id: str,
        unit: str,
        icon: str,
        precision: int,
        device_class: SensorDeviceClass | None = None,
        sensor_map: dict[str, list[str]] | None = None,
    ) -> None:
        super().__init__(hass, plant_name, plant_id, sensor_map)
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

    def __init__(
        self,
        hass: HomeAssistant,
        plant_name: str,
        plant_id: str,
        sensor_map: dict[str, list[str]] | None = None,
    ):
        super().__init__(
            hass,
            plant_name,
            plant_id,
            source_sensor=(sensor_map or {}).get("moisture_sensors")
            or f"sensor.{plant_id}_raw_moisture",
            name="Smoothed Moisture",
            unique_id=f"{plant_id}_smoothed_moisture",
            unit=UNIT_PERCENT,
            icon="mdi:water-percent",
            precision=1,
            device_class=SensorDeviceClass.MOISTURE,
            sensor_map=sensor_map,
        )

class DailyETSensor(HorticultureBaseSensor):
    """Sensor estimating daily ET (Evapotranspiration) loss."""
    def __init__(
        self,
        hass: HomeAssistant,
        plant_name: str,
        plant_id: str,
        sensor_map: dict[str, list[str]] | None = None,
    ):
        super().__init__(hass, plant_name, plant_id, sensor_map)
        self._attr_name = "Estimated Daily ET"
        self._attr_unique_id = f"{plant_id}_daily_et"
        self._attr_native_unit_of_measurement = UNIT_MM_DAY
        self._attr_device_class = SensorDeviceClass.PRECIPITATION
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:weather-sunny"
        self._attr_entity_category = CATEGORY_MONITORING

    async def async_update(self):
        """Calculate daily ET estimate (using a simple temperature/humidity formula)."""
        temp = self._get_state_value(self._sensor_map.get("temperature_sensors"))
        hum = self._get_state_value(self._sensor_map.get("humidity_sensors"))
        if temp is not None and hum is not None:
            et = max(0, (temp - 10) * (1 - hum / 100) * 0.5)
            self._attr_native_value = round(et, 1)
        else:
            _LOGGER.debug("Temp or humidity not available for ET calc, using default")
            # Fallback stub
            self._attr_native_value = 4.5

class RootZoneDepletionSensor(HorticultureBaseSensor):
    """Sensor estimating % root zone water depletion."""
    def __init__(
        self,
        hass: HomeAssistant,
        plant_name: str,
        plant_id: str,
        sensor_map: dict[str, list[str]] | None = None,
    ):
        super().__init__(hass, plant_name, plant_id, sensor_map)
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

    def __init__(
        self,
        hass: HomeAssistant,
        plant_name: str,
        plant_id: str,
        sensor_map: dict[str, list[str]] | None = None,
    ):
        super().__init__(
            hass,
            plant_name,
            plant_id,
            source_sensor=(sensor_map or {}).get("ec_sensors") or f"sensor.{plant_id}_raw_ec",
            name="Smoothed EC",
            unique_id=f"{plant_id}_smoothed_ec",
            unit="mS/cm",
            icon="mdi:water-outline",
            precision=2,
            sensor_map=sensor_map,
        )

class EstimatedFieldCapacitySensor(HorticultureBaseSensor):
    """Estimate of field capacity from past max moisture post-irrigation."""
    def __init__(
        self,
        hass: HomeAssistant,
        plant_name: str,
        plant_id: str,
        sensor_map: dict[str, list[str]] | None = None,
    ):
        super().__init__(hass, plant_name, plant_id, sensor_map)
        self._attr_name = "Estimated Field Capacity"
        self._attr_unique_id = f"{plant_id}_field_capacity"
        self._attr_native_unit_of_measurement = UNIT_PERCENT
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:water"
        self._attr_entity_category = CATEGORY_DIAGNOSTIC

    async def async_update(self):
        """Estimate field capacity (peak moisture over recent period)."""
        _LOGGER.debug("Estimating field capacity for plant: %s", self._plant_id)
        current = self._get_state_value(self._sensor_map.get("moisture_sensors"))
        if current is not None:
            max_val = getattr(self, "_max_moisture", None)
            self._max_moisture = current if max_val is None else max(max_val, current)
            self._attr_native_value = self._max_moisture
        else:
            self._attr_native_value = getattr(self, "_max_moisture", None)

class EstimatedWiltingPointSensor(HorticultureBaseSensor):
    """Estimate of permanent wilting point based on dry-down observation."""
    def __init__(
        self,
        hass: HomeAssistant,
        plant_name: str,
        plant_id: str,
        sensor_map: dict[str, list[str]] | None = None,
    ):
        super().__init__(hass, plant_name, plant_id, sensor_map)
        self._attr_name = "Estimated Wilting Point"
        self._attr_unique_id = f"{plant_id}_wilting_point"
        self._attr_native_unit_of_measurement = UNIT_PERCENT
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:water-off"
        self._attr_entity_category = CATEGORY_DIAGNOSTIC

    async def async_update(self):
        """Estimate wilting point (minimum moisture over recent period)."""
        _LOGGER.debug("Estimating wilting point for plant: %s", self._plant_id)
        current = self._get_state_value(self._sensor_map.get("moisture_sensors"))
        if current is not None:
            min_val = getattr(self, "_min_moisture", None)
            self._min_moisture = current if min_val is None else min(min_val, current)
            self._attr_native_value = self._min_moisture
        else:
            self._attr_native_value = getattr(self, "_min_moisture", None)

class DailyNitrogenAppliedSensor(HorticultureBaseSensor):
    """Amount of nitrogen applied to plant today."""
    def __init__(
        self,
        hass: HomeAssistant,
        plant_name: str,
        plant_id: str,
        sensor_map: dict[str, list[str]] | None = None,
    ):
        super().__init__(hass, plant_name, plant_id, sensor_map)
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
    def __init__(
        self,
        hass: HomeAssistant,
        plant_name: str,
        plant_id: str,
        sensor_map: dict[str, list[str]] | None = None,
    ):
        super().__init__(hass, plant_name, plant_id, sensor_map)
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
    def __init__(
        self,
        hass: HomeAssistant,
        plant_name: str,
        plant_id: str,
        sensor_map: dict[str, list[str]] | None = None,
    ):
        super().__init__(hass, plant_name, plant_id, sensor_map)
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


class _EnvironmentEvaluationSensor(HorticultureBaseSensor):
    """Base helper for sensors evaluating environment data."""

    NAME: str = ""
    UNIQUE_KEY: str = ""
    ICON: str = "mdi:leaf"

    def __init__(
        self,
        hass: HomeAssistant,
        plant_name: str,
        plant_id: str,
        sensor_map: dict[str, list[str]] | None = None,
    ) -> None:
        super().__init__(hass, plant_name, plant_id, sensor_map)
        self._attr_name = self.NAME
        self._attr_unique_id = f"{plant_id}_{self.UNIQUE_KEY}"
        self._attr_icon = self.ICON
        self._attr_entity_category = CATEGORY_DIAGNOSTIC

    def _gather_environment(self) -> dict[str, float]:
        """Return available raw environment readings for this plant."""
        sensors = {
            "temp_c": self._sensor_map.get("temperature_sensors"),
            "humidity_pct": self._sensor_map.get("humidity_sensors"),
            "light_ppfd": self._sensor_map.get("light_sensors"),
            "co2_ppm": self._sensor_map.get("co2_sensors"),
        }
        return {
            key: val
            for key in sensors
            if (val := self._get_state_value(sensors[key])) is not None
        }

    def _compute(self, env: dict[str, float], plant_type: str):
        raise NotImplementedError

    async def async_update(self) -> None:
        env = self._gather_environment()
        if len(env) < 2:
            self._attr_native_value = None
            return
        plant_type = get_plant_type(self._plant_id, self.hass) or "citrus"
        self._attr_native_value = self._compute(env, plant_type)


class EnvironmentScoreSensor(_EnvironmentEvaluationSensor):
    """Sensor providing a 0-100 environment score."""

    NAME = "Environment Score"
    UNIQUE_KEY = "env_score"
    ICON = "mdi:gauge"

    def _compute(self, env: dict[str, float], plant_type: str):
        score = score_environment(env, plant_type)
        return round(score, 1)


class EnvironmentQualitySensor(_EnvironmentEvaluationSensor):
    """Sensor providing a ``good``/``fair``/``poor`` quality rating."""

    NAME = "Environment Quality"
    UNIQUE_KEY = "env_quality"

    def _compute(self, env: dict[str, float], plant_type: str):
        return classify_environment_quality(env, plant_type)

