"""Binary sensor platform for Horticulture Assistant."""
import logging

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    DEVICE_CLASS_PROBLEM,
    DEVICE_CLASS_MOISTURE,
    DEVICE_CLASS_SAFETY,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, CATEGORY_DIAGNOSTIC, CATEGORY_CONTROL
from .entity_base import HorticultureBaseEntity
from .utils.state_helpers import normalize_entities

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up horticulture assistant binary sensors from a config entry."""
    _LOGGER.debug("Setting up horticulture_assistant binary sensors")
    plant_id = entry.entry_id
    plant_name = f"Plant {plant_id[:6]}"

    sensor_map = {
        "moisture_sensors": normalize_entities(
            entry.data.get("moisture_sensors"), f"sensor.{plant_id}_raw_moisture"
        ),
        "temperature_sensors": normalize_entities(
            entry.data.get("temperature_sensors"), f"sensor.{plant_id}_raw_temperature"
        ),
        "humidity_sensors": normalize_entities(
            entry.data.get("humidity_sensors"), f"sensor.{plant_id}_raw_humidity"
        ),
        "ec_sensors": normalize_entities(
            entry.data.get("ec_sensors"), f"sensor.{plant_id}_raw_ec"
        ),
    }

    sensors: list[BinarySensorEntity] = [
        SensorHealthBinarySensor(hass, plant_name, plant_id, sensor_map),
        IrrigationReadinessBinarySensor(hass, plant_name, plant_id, sensor_map),
        FaultDetectionBinarySensor(hass, plant_name, plant_id, sensor_map),
    ]

    async_add_entities(sensors)


class HorticultureBaseBinarySensor(HorticultureBaseEntity, BinarySensorEntity):
    """Base class for horticulture binary sensors."""

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
            sensor_map = {
                "moisture_sensors": [f"sensor.{plant_id}_raw_moisture"],
                "temperature_sensors": [f"sensor.{plant_id}_raw_temperature"],
                "humidity_sensors": [f"sensor.{plant_id}_raw_humidity"],
                "ec_sensors": [f"sensor.{plant_id}_raw_ec"],
            }
        self._sensor_map = sensor_map


class SensorHealthBinarySensor(HorticultureBaseBinarySensor):
    """Binary sensor to indicate overall sensor health (any raw sensor offline)."""

    def __init__(
        self,
        hass: HomeAssistant,
        plant_name: str,
        plant_id: str,
        sensor_map: dict[str, list[str]] | None = None,
    ):
        super().__init__(hass, plant_name, plant_id, sensor_map)
        self._attr_name = "Sensor Health"
        self._attr_unique_id = f"{plant_id}_sensor_health"
        self._attr_device_class = DEVICE_CLASS_PROBLEM
        self._attr_icon = "mdi:heart-pulse"
        self._attr_entity_category = CATEGORY_DIAGNOSTIC

    async def async_update(self):
        """Check if raw sensors are online (no missing or unavailable sensors)."""
        # List of expected raw sensor entity IDs
        raw_ids = (
            self._sensor_map.get("moisture_sensors", [])
            + self._sensor_map.get("temperature_sensors", [])
            + self._sensor_map.get("humidity_sensors", [])
            + self._sensor_map.get("ec_sensors", [])
        )
        problem = False
        for entity_id in raw_ids:
            state = self.hass.states.get(entity_id)
            if not state or state.state in ("unknown", "unavailable"):
                _LOGGER.debug("Raw sensor unavailable: %s", entity_id)
                problem = True
                break

        # device_class 'problem': True means problem, False means OK
        self._attr_is_on = problem


class IrrigationReadinessBinarySensor(HorticultureBaseBinarySensor):
    """Binary sensor to indicate if irrigation should run (root zone dry)."""

    def __init__(
        self,
        hass: HomeAssistant,
        plant_name: str,
        plant_id: str,
        sensor_map: dict[str, list[str]] | None = None,
    ):
        super().__init__(hass, plant_name, plant_id, sensor_map)
        self._attr_name = "Irrigation Readiness"
        self._attr_unique_id = f"{plant_id}_irrigation_readiness"
        self._attr_device_class = DEVICE_CLASS_MOISTURE
        self._attr_icon = "mdi:water-alert"
        self._attr_entity_category = CATEGORY_CONTROL
        # Threshold for root zone depletion (%)
        self._threshold = 70.0

    async def async_update(self):
        """Determine if root zone is dry enough for watering."""
        depletion_id = f"sensor.{self._plant_id}_depletion"
        state = self.hass.states.get(depletion_id)
        if not state or state.state in ("unknown", "unavailable"):
            _LOGGER.debug("Root zone depletion sensor not available: %s", depletion_id)
            self._attr_is_on = False
            return

        try:
            depletion = float(state.state)
        except (ValueError, TypeError):
            _LOGGER.error("Invalid root zone depletion value: %s", state.state)
            self._attr_is_on = False
            return

        # If depletion above threshold, root zone is dry => irrigation ready
        self._attr_is_on = depletion > self._threshold


class FaultDetectionBinarySensor(HorticultureBaseBinarySensor):
    """Binary sensor to detect faults (sensor out of bounds or removed)."""

    def __init__(
        self,
        hass: HomeAssistant,
        plant_name: str,
        plant_id: str,
        sensor_map: dict[str, list[str]] | None = None,
    ):
        super().__init__(hass, plant_name, plant_id, sensor_map)
        self._attr_name = "Fault Detection"
        self._attr_unique_id = f"{plant_id}_fault_detection"
        self._attr_device_class = DEVICE_CLASS_SAFETY
        self._attr_icon = "mdi:alert"
        self._attr_entity_category = CATEGORY_DIAGNOSTIC

    async def async_update(self):
        """Check for sensor faults or out-of-range values."""
        # Expected sensors and their valid ranges
        checks = []
        for eid in self._sensor_map.get("moisture_sensors", []):
            checks.append((eid, 0.0, 100.0))
        for eid in self._sensor_map.get("humidity_sensors", []):
            checks.append((eid, 0.0, 100.0))
        for eid in self._sensor_map.get("temperature_sensors", []):
            checks.append((eid, -50.0, 60.0))
        for eid in self._sensor_map.get("ec_sensors", []):
            checks.append((eid, 0.0, 50.0))
        fault = False
        for entity_id, min_val, max_val in checks:
            state = self.hass.states.get(entity_id)
            if not state or state.state in ("unknown", "unavailable"):
                _LOGGER.debug("Fault detected (missing sensor): %s", entity_id)
                fault = True
                break
            try:
                value = float(state.state)
            except (ValueError, TypeError):
                _LOGGER.warning("Invalid sensor value: %s = %s", entity_id, state.state)
                fault = True
                break
            # Check value bounds
            if value < min_val or value > max_val:
                _LOGGER.warning(
                    "Sensor %s out of range: %s not in [%s, %s]",
                    entity_id, value, min_val, max_val
                )
                fault = True
                break

        # device_class 'safety': True means unsafe (fault), False means safe
        self._attr_is_on = fault
