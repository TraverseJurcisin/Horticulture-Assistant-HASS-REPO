import importlib.util
import sys
import types
from pathlib import Path

import pytest

from custom_components.horticulture_assistant.engine.metrics import dew_point_c, lux_to_ppfd, vpd_kpa
from custom_components.horticulture_assistant.utils import state_helpers

pkg = types.ModuleType("custom_components.horticulture_assistant")
pkg.__path__ = [str(Path(__file__).resolve().parents[1] / "custom_components" / "horticulture_assistant")]
sys.modules.setdefault("custom_components.horticulture_assistant", pkg)

spec = importlib.util.spec_from_file_location(
    "custom_components.horticulture_assistant.coordinator",
    Path(__file__).resolve().parents[1] / "custom_components" / "horticulture_assistant" / "coordinator.py",
)
coordinator_mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(coordinator_mod)
HorticultureCoordinator = coordinator_mod.HorticultureCoordinator
UnitOfTemperature = coordinator_mod.UnitOfTemperature
TemperatureConverter = coordinator_mod.TemperatureConverter


def test_state_helpers_import_and_get_numeric_state():
    hass = types.SimpleNamespace(
        states=types.SimpleNamespace(get=lambda entity_id: types.SimpleNamespace(state="12.5"))
    )

    value = state_helpers.get_numeric_state(hass, "sensor.example")
    assert value == 12.5


def test_get_numeric_state_handles_decimal_comma():
    hass = types.SimpleNamespace(states=types.SimpleNamespace(get=lambda entity_id: types.SimpleNamespace(state="5,5")))

    value = state_helpers.get_numeric_state(hass, "sensor.decimal")
    assert value == pytest.approx(5.5)


def test_get_numeric_state_handles_thousand_separators():
    hass = types.SimpleNamespace(
        states=types.SimpleNamespace(get=lambda entity_id: types.SimpleNamespace(state="1,234.56"))
    )

    value = state_helpers.get_numeric_state(hass, "sensor.thousands")
    assert value == pytest.approx(1234.56)


def test_get_numeric_state_handles_dotted_thousands():
    hass = types.SimpleNamespace(
        states=types.SimpleNamespace(get=lambda entity_id: types.SimpleNamespace(state="1.234.567"))
    )

    value = state_helpers.get_numeric_state(hass, "sensor.dotted")
    assert value == pytest.approx(1_234_567)


def test_get_numeric_state_handles_european_format():
    hass = types.SimpleNamespace(
        states=types.SimpleNamespace(get=lambda entity_id: types.SimpleNamespace(state="1.234,56"))
    )

    value = state_helpers.get_numeric_state(hass, "sensor.euro")
    assert value == pytest.approx(1234.56)


def test_get_numeric_state_handles_unicode_whitespace():
    hass = types.SimpleNamespace(
        states=types.SimpleNamespace(get=lambda entity_id: types.SimpleNamespace(state="1\u00a0234,5"))
    )

    value = state_helpers.get_numeric_state(hass, "sensor.nbsp")
    assert value == pytest.approx(1234.5)


def test_get_numeric_state_handles_unicode_signs():
    """Unicode minus/plus signs should be normalised before conversion."""

    states = {
        "sensor.negative": types.SimpleNamespace(state="−12,5"),
        "sensor.scientific": types.SimpleNamespace(state="3e−2"),
        "sensor.positive": types.SimpleNamespace(state="＋7"),
    }

    hass = types.SimpleNamespace(states=types.SimpleNamespace(get=lambda entity_id: states.get(entity_id)))

    assert state_helpers.get_numeric_state(hass, "sensor.negative") == pytest.approx(-12.5)
    assert state_helpers.get_numeric_state(hass, "sensor.scientific") == pytest.approx(0.03)
    assert state_helpers.get_numeric_state(hass, "sensor.positive") == pytest.approx(7.0)


def test_parse_entities_ignores_none_and_blank_entries():
    """None values or blank strings should be removed when parsing entities."""

    entities = state_helpers.parse_entities([None, "  ", "sensor.one", "sensor.one", "", None])

    assert entities == ["sensor.one"]


def test_parse_entities_handles_mixed_iterables():
    """Non-string iterable members should be coerced while ignoring falsy items."""

    entities = state_helpers.parse_entities(["sensor.one", Path("sensor.two"), None, ""])

    assert entities == ["sensor.one", "sensor.two"]


@pytest.mark.asyncio
async def test_coordinator_converts_fahrenheit_to_celsius(hass, monkeypatch):
    """Fahrenheit temperature states should be converted before computing metrics."""

    def fake_convert(value, from_unit, to_unit):
        if from_unit == UnitOfTemperature.FAHRENHEIT and to_unit == UnitOfTemperature.CELSIUS:
            return (float(value) - 32.0) * 5.0 / 9.0
        return value

    monkeypatch.setattr(TemperatureConverter, "convert", staticmethod(fake_convert))

    entry = types.SimpleNamespace(entry_id="entry", options={}, data={})
    coordinator = HorticultureCoordinator(hass, entry)

    hass.states.async_set("sensor.temp_f", "77", {"unit_of_measurement": "F"})
    hass.states.async_set("sensor.humidity", "60")

    metrics = await coordinator._compute_metrics(
        "plant1",
        {
            "sensors": {
                "temperature": "sensor.temp_f",
                "humidity": "sensor.humidity",
            }
        },
    )

    assert metrics["dew_point"] == pytest.approx(16.7, rel=1e-2)
    assert metrics["vpd"] == pytest.approx(1.27, rel=1e-2)


@pytest.mark.asyncio
async def test_coordinator_handles_sequence_sensor_bindings(hass):
    """Coordinator should gracefully handle sequence sensor mappings."""

    entry = types.SimpleNamespace(entry_id="entry", options={}, data={})
    coordinator = HorticultureCoordinator(hass, entry)

    hass.states.async_set("sensor.light_primary", "250")
    hass.states.async_set("sensor.temp_primary", "21")
    hass.states.async_set("sensor.humidity_main", "55")
    hass.states.async_set("sensor.moisture_probe", "40")

    metrics = await coordinator._compute_metrics(
        "plant_sequence",
        {
            "sensors": {
                "illuminance": [None, "  sensor.light_primary  "],
                "temperature": ("sensor.temp_primary", "sensor.temp_backup"),
                "humidity": ["sensor.humidity_main"],
                "moisture": ["", "sensor.moisture_probe"],
            }
        },
    )

    assert metrics["ppfd"] == pytest.approx(lux_to_ppfd(250))
    assert metrics["moisture"] == pytest.approx(40)


@pytest.mark.asyncio
async def test_coordinator_parses_units_in_sensor_states(hass):
    """Sensor states containing units should still be interpreted as numeric."""

    entry = types.SimpleNamespace(entry_id="entry", options={}, data={})
    coordinator = HorticultureCoordinator(hass, entry)

    hass.states.async_set("sensor.light_units", "200 lx")
    hass.states.async_set("sensor.temp_units", "22 °C", {"unit_of_measurement": "°C"})
    hass.states.async_set("sensor.humidity_units", "55 %")
    hass.states.async_set("sensor.moisture_units", "40 %")

    metrics = await coordinator._compute_metrics(
        "profile_units",
        {
            "sensors": {
                "illuminance": "sensor.light_units",
                "temperature": "sensor.temp_units",
                "humidity": "sensor.humidity_units",
                "moisture": "sensor.moisture_units",
            }
        },
    )

    expected_temp_c = 22.0
    assert metrics["ppfd"] == pytest.approx(lux_to_ppfd(200))
    assert metrics["dew_point"] == pytest.approx(dew_point_c(expected_temp_c, 55.0), rel=1e-4)
    assert metrics["vpd"] == pytest.approx(vpd_kpa(expected_temp_c, 55.0), rel=1e-4)
    assert metrics["moisture"] == pytest.approx(40)
