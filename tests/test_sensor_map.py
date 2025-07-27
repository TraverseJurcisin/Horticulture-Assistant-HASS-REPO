import types
import sys

# Minimal Home Assistant stub so the module imports without the real package
ha = types.ModuleType("homeassistant")
ha.core = types.ModuleType("homeassistant.core")
ha.core.HomeAssistant = object
sys.modules.setdefault("homeassistant", ha)
sys.modules.setdefault("homeassistant.core", ha.core)

from custom_components.horticulture_assistant.utils.sensor_map import build_sensor_map, DEFAULT_SENSORS


def test_build_sensor_map_defaults():
    result = build_sensor_map({}, "pid")
    expected = {k: [v.format(plant_id="pid")] for k, v in DEFAULT_SENSORS.items()}
    assert result == expected


def test_build_sensor_map_custom_entries():
    data = {
        "moisture_sensors": "sensor.a, sensor.b",
        "ec_sensors": ["sensor.ec1", "sensor.ec2"],
    }
    result = build_sensor_map(data, "pid", keys=("moisture_sensors", "ec_sensors"))
    assert result == {
        "moisture_sensors": ["sensor.a", "sensor.b"],
        "ec_sensors": ["sensor.ec1", "sensor.ec2"],
    }
