import types
import sys

# Provide minimal 'homeassistant.core' stub so the helper module imports cleanly
ha = types.ModuleType("homeassistant")
ha.core = types.ModuleType("homeassistant.core")
ha.core.HomeAssistant = object
sys.modules.setdefault("homeassistant", ha)
sys.modules.setdefault("homeassistant.core", ha.core)

from custom_components.horticulture_assistant.utils.state_helpers import (
    get_numeric_state,
    normalize_entities,
    aggregate_sensor_values,
)


class DummyStates:
    def __init__(self):
        self._data = {}

    def get(self, entity_id):
        val = self._data.get(entity_id)
        return types.SimpleNamespace(state=val) if val is not None else None


class DummyHass:
    def __init__(self):
        self.states = DummyStates()


def test_get_numeric_state_basic():
    hass = DummyHass()
    hass.states._data["sensor.number"] = "5"
    assert get_numeric_state(hass, "sensor.number") == 5.0


def test_get_numeric_state_with_units():
    hass = DummyHass()
    hass.states._data["sensor.temp"] = "21.5 °C"
    assert get_numeric_state(hass, "sensor.temp") == 21.5


def test_get_numeric_state_commas_and_spaces():
    hass = DummyHass()
    hass.states._data["sensor.comma"] = "1,234.5 ppm"
    assert get_numeric_state(hass, "sensor.comma") == 1234.5


def test_get_numeric_state_invalid():
    hass = DummyHass()
    hass.states._data["sensor.bad"] = "unknown"
    assert get_numeric_state(hass, "sensor.bad") is None
    hass.states._data["sensor.bad"] = "foo"
    assert get_numeric_state(hass, "sensor.bad") is None


def test_normalize_entities_split_and_unique():
    result = normalize_entities("sensor.a, sensor.b; sensor.a", "sensor.default")
    assert result == ["sensor.a", "sensor.b"]


def test_aggregate_sensor_values_average_and_median():
    hass = DummyHass()
    hass.states._data = {
        "sensor.one": "10",
        "sensor.two": "20",
        "sensor.three": "30",
    }
    avg = aggregate_sensor_values(hass, ["sensor.one", "sensor.two"])
    assert avg == 15.0
    med = aggregate_sensor_values(hass, ["sensor.one", "sensor.two", "sensor.three"])
    assert med == 20.0
