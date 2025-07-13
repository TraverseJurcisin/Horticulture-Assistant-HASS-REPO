import os
import json
import logging
from datetime import timedelta
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, CoordinatorEntity
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.entity_platform import AddEntitiesCallback

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(hours=1)
REPORT_DIR = "data/reports"

async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    sensors = []

    if not os.path.exists(REPORT_DIR):
        _LOGGER.warning("No report directory found.")
        return

    for fname in os.listdir(REPORT_DIR):
        if not fname.endswith(".json"):
            continue
        plant_id = fname.replace(".json", "")
        report_path = os.path.join(REPORT_DIR, fname)

        try:
            with open(report_path, "r") as f:
                data = json.load(f)
        except Exception as e:
            _LOGGER.error(f"Could not load {fname}: {e}")
            continue

        # Growth / VGI
        g = data.get("growth", {})
        sensors.append(HortiSensor(plant_id, "vgi_today", g.get("vgi_today", 0), "index"))
        sensors.append(HortiSensor(plant_id, "vgi_total", g.get("vgi_total", 0), "index"))

        # Transpiration
        sensors.append(HortiSensor(plant_id, "transpiration_ml_day", data.get("transpiration", {}).get("transpiration_ml_day", 0), "mL"))

        # Water deficit
        w = data.get("water_deficit", {})
        sensors.append(HortiSensor(plant_id, "ml_available", w.get("ml_available", 0), "mL"))
        sensors.append(HortiSensor(plant_id, "depletion_pct", round(w.get("depletion_pct", 0) * 100, 1), "%"))
        sensors.append(HortiSensor(plant_id, "mad_crossed", int(w.get("mad_crossed", False)), ""))

        # Rootzone depth
        rz = data.get("rootzone", {})
        sensors.append(HortiSensor(plant_id, "root_depth_cm", rz.get("root_depth_cm", 0), "cm"))
        sensors.append(HortiSensor(plant_id, "available_water_ml", rz.get("total_available_water_ml", 0), "mL"))

        # NUE
        nue = data.get("nue", {}).get("nue", {})
        for nutrient, val in nue.items():
            sensors.append(HortiSensor(plant_id, f"nue_{nutrient.lower()}", val, "g/g"))

        # Thresholds
        t = data.get("thresholds", {})
        for nutrient, val in t.items():
            sensors.append(HortiSensor(plant_id, f"threshold_{nutrient.lower()}", val, "ppm"))

    async_add_entities(sensors)

class HortiSensor(Entity):
    def __init__(self, plant_id: str, sensor_type: str, value, unit: str):
        self._attr_name = f"{plant_id} {sensor_type.replace('_', ' ').title()}"
        self._attr_unique_id = f"{plant_id}_{sensor_type}"
        self._state = value
        self._unit = unit

    @property
    def state(self):
        return self._state

    @property
    def unit_of_measurement(self):
        return self._unit

    @property
    def should_poll(self):
        return False

    @property
    def icon(self):
        return "mdi:leaf"
