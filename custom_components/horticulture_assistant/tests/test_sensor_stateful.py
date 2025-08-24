import asyncio
import importlib.util
import sys
import types
from datetime import datetime
from pathlib import Path

MODULE_PATH = (
    Path(__file__).resolve().parents[3] / "custom_components/horticulture_assistant/sensor.py"
)
PACKAGE = "custom_components.horticulture_assistant"
if PACKAGE not in sys.modules:
    sys.modules[PACKAGE] = types.ModuleType(PACKAGE)
CONST_PATH = (
    Path(__file__).resolve().parents[3] / "custom_components/horticulture_assistant/const.py"
)
const_spec = importlib.util.spec_from_file_location(f"{PACKAGE}.const", CONST_PATH)
const_mod = importlib.util.module_from_spec(const_spec)
sys.modules[const_spec.name] = const_mod
const_spec.loader.exec_module(const_mod)

spec = importlib.util.spec_from_file_location(f"{PACKAGE}.sensor", MODULE_PATH)
sensor = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = sensor

# minimal stubs for Home Assistant imports used in sensor.py
ha = types.ModuleType("homeassistant")
ha.components = types.ModuleType("homeassistant.components")
ha_sensor_mod = types.ModuleType("homeassistant.components.sensor")


class SensorEntity:
    def __init__(self):
        self._attr_native_value = None

    @property
    def native_value(self):
        return getattr(self, "_attr_native_value", None)


class SensorDeviceClass:
    MOISTURE = "moisture"
    PRECIPITATION = "precipitation"
    WEIGHT = "weight"


class SensorStateClass:
    MEASUREMENT = "measurement"


ha_sensor_mod.SensorEntity = SensorEntity
ha_sensor_mod.SensorDeviceClass = SensorDeviceClass
ha_sensor_mod.SensorStateClass = SensorStateClass
ha.components.sensor = ha_sensor_mod
ha.config_entries = types.ModuleType("homeassistant.config_entries")
ha.config_entries.ConfigEntry = object
ha.core = types.ModuleType("homeassistant.core")
ha.core.HomeAssistant = object
ha.helpers = types.ModuleType("homeassistant.helpers")
ha.helpers.entity_platform = types.ModuleType("homeassistant.helpers.entity_platform")
ha.helpers.entity_platform.AddEntitiesCallback = object
ha.helpers.entity = types.ModuleType("homeassistant.helpers.entity")
ha.helpers.entity.Entity = object
ha.const = types.ModuleType("homeassistant.const")
ha.const.UnitOfMass = types.SimpleNamespace(GRAMS="g", MILLIGRAMS="mg")
sys.modules.setdefault("homeassistant", ha)
sys.modules.setdefault("homeassistant.components", ha.components)
sys.modules.setdefault("homeassistant.components.sensor", ha_sensor_mod)
sys.modules.setdefault("homeassistant.config_entries", ha.config_entries)
sys.modules.setdefault("homeassistant.core", ha.core)
sys.modules.setdefault("homeassistant.helpers", ha.helpers)
sys.modules.setdefault("homeassistant.helpers.entity", ha.helpers.entity)
sys.modules.setdefault("homeassistant.helpers.entity_platform", ha.helpers.entity_platform)
sys.modules.setdefault("homeassistant.const", ha.const)

spec.loader.exec_module(sensor)

NutrientTracker = importlib.import_module(
    "custom_components.horticulture_assistant.utils.nutrient_tracker"
).NutrientTracker
NutrientDeliveryRecord = importlib.import_module(
    "custom_components.horticulture_assistant.utils.nutrient_tracker"
).NutrientDeliveryRecord

EstimatedFieldCapacitySensor = sensor.EstimatedFieldCapacitySensor
EstimatedWiltingPointSensor = sensor.EstimatedWiltingPointSensor
DailyNitrogenAppliedSensor = sensor.DailyNitrogenAppliedSensor
DOMAIN = sensor.DOMAIN


class DummyStates:
    def __init__(self):
        self._data = {}

    def get(self, eid):
        val = self._data.get(eid)
        return types.SimpleNamespace(state=val) if val is not None else None


class DummyHass:
    def __init__(self):
        self.states = DummyStates()
        self.bus = types.SimpleNamespace(async_listen=lambda *a, **k: None)
        self.data = {DOMAIN: {"nutrient_tracker": NutrientTracker()}}


def test_field_capacity_and_wilting_point():
    hass = DummyHass()
    fc = EstimatedFieldCapacitySensor(hass, "Plant", "pid")
    wp = EstimatedWiltingPointSensor(hass, "Plant", "pid")

    hass.states._data["sensor.pid_raw_moisture"] = "40"
    asyncio.run(fc.async_update())
    asyncio.run(wp.async_update())
    assert fc.native_value == 40
    assert wp.native_value == 40

    hass.states._data["sensor.pid_raw_moisture"] = "35"
    asyncio.run(fc.async_update())
    asyncio.run(wp.async_update())
    assert fc.native_value == 40
    assert wp.native_value == 35

    hass.states._data["sensor.pid_raw_moisture"] = "50"
    asyncio.run(fc.async_update())
    asyncio.run(wp.async_update())
    assert fc.native_value == 50
    assert wp.native_value == 35


def test_daily_nitrogen_applied():
    hass = DummyHass()
    tracker = hass.data[DOMAIN]["nutrient_tracker"]
    now = datetime.now()
    tracker.delivery_log.append(NutrientDeliveryRecord("pid", "b1", now, {"N": 50}, 2.0))
    tracker.delivery_log.append(NutrientDeliveryRecord("other", "b2", now, {"N": 30}, 1.0))
    sensor_entity = DailyNitrogenAppliedSensor(hass, "Plant", "pid")
    asyncio.run(sensor_entity.async_update())
    assert sensor_entity.native_value == 100.0
    tracker.delivery_log.append(NutrientDeliveryRecord("pid", "b3", now, {"N": 20}, 1.0))
    asyncio.run(sensor_entity.async_update())
    assert sensor_entity.native_value == 120.0
