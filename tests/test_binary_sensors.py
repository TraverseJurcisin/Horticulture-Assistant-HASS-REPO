import asyncio
import importlib.util
import sys
import types
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "custom_components/horticulture_assistant/binary_sensor.py"
PACKAGE = "custom_components.horticulture_assistant"
if PACKAGE not in sys.modules:
    pkg = types.ModuleType(PACKAGE)
    pkg.__path__ = [str(Path(__file__).resolve().parents[1] / "custom_components/horticulture_assistant")]
    sys.modules[PACKAGE] = pkg
CONST_PATH = Path(__file__).resolve().parents[1] / "custom_components/horticulture_assistant/const.py"
const_spec = importlib.util.spec_from_file_location(f"{PACKAGE}.const", CONST_PATH)
const_mod = importlib.util.module_from_spec(const_spec)
sys.modules[const_spec.name] = const_mod
const_spec.loader.exec_module(const_mod)

spec = importlib.util.spec_from_file_location(f"{PACKAGE}.binary_sensor", MODULE_PATH)
binary_sensor = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = binary_sensor

# Home Assistant stubs
ha = types.ModuleType("homeassistant")
ha.components = types.ModuleType("homeassistant.components")
ha_bs_mod = types.ModuleType("homeassistant.components.binary_sensor")
class BinarySensorEntity:
    def __init__(self):
        self._attr_is_on = False
        self._attr_name = ""
    @property
    def is_on(self):
        return self._attr_is_on
ha_bs_mod.BinarySensorEntity = BinarySensorEntity
ha_bs_mod.DEVICE_CLASS_PROBLEM = "problem"
ha_bs_mod.DEVICE_CLASS_MOISTURE = "moisture"
ha_bs_mod.DEVICE_CLASS_SAFETY = "safety"
ha.components.binary_sensor = ha_bs_mod
ha.config_entries = types.ModuleType("homeassistant.config_entries")
ha.config_entries.ConfigEntry = object
ha.core = types.ModuleType("homeassistant.core")
ha.core.HomeAssistant = object
ha.helpers = types.ModuleType("homeassistant.helpers")
ha.helpers.entity_platform = types.ModuleType("homeassistant.helpers.entity_platform")
ha.helpers.entity_platform.AddEntitiesCallback = object
sys.modules.setdefault("homeassistant", ha)
sys.modules.setdefault("homeassistant.components", ha.components)
sys.modules.setdefault("homeassistant.components.binary_sensor", ha_bs_mod)
sys.modules.setdefault("homeassistant.config_entries", ha.config_entries)
sys.modules.setdefault("homeassistant.core", ha.core)
sys.modules.setdefault("homeassistant.helpers", ha.helpers)
sys.modules.setdefault("homeassistant.helpers.entity_platform", ha.helpers.entity_platform)

spec.loader.exec_module(binary_sensor)

SensorHealthBinarySensor = binary_sensor.SensorHealthBinarySensor
IrrigationReadinessBinarySensor = binary_sensor.IrrigationReadinessBinarySensor
FaultDetectionBinarySensor = binary_sensor.FaultDetectionBinarySensor

class DummyStates:
    def __init__(self):
        self._data = {}
    def get(self, eid):
        val = self._data.get(eid)
        return types.SimpleNamespace(state=val) if val is not None else None

class DummyHass:
    def __init__(self):
        self.states = DummyStates()

def test_binary_sensor_behaviour():
    hass = DummyHass()
    health = SensorHealthBinarySensor(hass, "Plant", "pid")
    readiness = IrrigationReadinessBinarySensor(hass, "Plant", "pid")
    fault = FaultDetectionBinarySensor(hass, "Plant", "pid")

    # Sensor health - missing raw sensor triggers problem
    asyncio.run(health.async_update())
    assert health.is_on  # all sensors missing
    hass.states._data = {
        "sensor.pid_raw_moisture": "40",
        "sensor.pid_raw_temperature": "22",
        "sensor.pid_raw_humidity": "60",
        "sensor.pid_raw_ec": "1.2",
    }
    asyncio.run(health.async_update())
    assert not health.is_on

    # Irrigation readiness based on depletion
    hass.states._data["sensor.pid_depletion"] = "75"
    asyncio.run(readiness.async_update())
    assert readiness.is_on
    hass.states._data["sensor.pid_depletion"] = "65"
    asyncio.run(readiness.async_update())
    assert not readiness.is_on

    # Fault detection out of range
    asyncio.run(fault.async_update())
    assert not fault.is_on
    hass.states._data["sensor.pid_raw_temperature"] = "100"  # out of range
    asyncio.run(fault.async_update())
    assert fault.is_on
