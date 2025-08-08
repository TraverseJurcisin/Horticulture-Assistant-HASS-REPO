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
    parse_entities,
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


def test_parse_entities_dedup_and_strip():
    result = parse_entities("sensor.a ; sensor.b, sensor.a")
    assert result == ["sensor.a", "sensor.b"]


def test_parse_entities_iterable_and_empty():
    result = parse_entities(["sensor.a", "", "sensor.b", "sensor.a"])
    assert result == ["sensor.a", "sensor.b"]
    assert parse_entities(None) == []


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


def test_get_numeric_state_negative():
    hass = DummyHass()
    hass.states._data["sensor.negative"] = "-12.7 pH"
    assert get_numeric_state(hass, "sensor.negative") == -12.7


def test_normalize_entities_split_and_unique():
    result = normalize_entities("sensor.a, sensor.b; sensor.a", "sensor.default")
    assert result == ["sensor.a", "sensor.b"]


def test_normalize_entities_iterable_and_default():
    result = normalize_entities(
        ["sensor.a", "sensor.b", "sensor.a", "sensor.c"], "sensor.default"
    )
    assert result == ["sensor.a", "sensor.b", "sensor.c"]
    assert normalize_entities(None, "sensor.default") == ["sensor.default"]


def test_normalize_entities_empty_inputs():
    assert normalize_entities("", "sensor.default") == ["sensor.default"]
    assert normalize_entities([], "sensor.default") == ["sensor.default"]


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


def test_aggregate_sensor_values_ignores_invalid_and_none_when_all_invalid():
    hass = DummyHass()
    hass.states._data = {
        "sensor.good": "10",
        "sensor.bad1": "unknown",
        "sensor.bad2": "foo",
    }
    ids = (eid for eid in ["sensor.good", "sensor.bad1", "sensor.bad2"])
    assert aggregate_sensor_values(hass, ids) == 10.0
    assert aggregate_sensor_values(hass, ["sensor.bad1", "sensor.bad2"]) is None


def test_aggregate_sensor_values_deduplicates_ids():
    hass = DummyHass()
    hass.states._data = {
        "sensor.one": "10",
        "sensor.two": "20",
    }
    # Duplicate sensors should not skew the average
    result = aggregate_sensor_values(hass, ["sensor.one", "sensor.one", "sensor.two"])
    assert result == 15.0


def test_aggregate_sensor_values_parses_delimited_string():
    hass = DummyHass()
    hass.states._data = {
        "sensor.one": "10",
        "sensor.two": "20",
    }
    result = aggregate_sensor_values(hass, "sensor.one; sensor.one, sensor.two")
    assert result == 15.0
    assert aggregate_sensor_values(hass, "") is None


def test_aggregate_sensor_values_skips_blank_entries():
    hass = DummyHass()
    hass.states._data = {"sensor.one": "10"}
    # A mixture of delimiters and empty segments should resolve to just sensor.one
    assert aggregate_sensor_values(hass, "sensor.one, ,; ;") == 10.0
