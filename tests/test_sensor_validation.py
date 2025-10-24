import sys
import types
from enum import Enum

import pytest

ha_module = sys.modules.setdefault("homeassistant", types.ModuleType("homeassistant"))
components_module = sys.modules.setdefault(
    "homeassistant.components", types.ModuleType("homeassistant.components")
)
sensor_module = types.ModuleType("homeassistant.components.sensor")


class _StubSensorEntity:
    pass


class _StubSensorStateClass(str, Enum):
    MEASUREMENT = "measurement"


class _StubSensorDeviceClass(str, Enum):
    TEMPERATURE = "temperature"
    HUMIDITY = "humidity"
    ILLUMINANCE = "illuminance"
    MOISTURE = "moisture"
    CO2 = "co2"
    PH = "ph"
    CONDUCTIVITY = "conductivity"


sensor_module.SensorEntity = _StubSensorEntity
sensor_module.SensorStateClass = _StubSensorStateClass
sensor_module.SensorDeviceClass = _StubSensorDeviceClass
components_module.sensor = sensor_module
ha_module.components = components_module
sys.modules["homeassistant.components.sensor"] = sensor_module

from custom_components.horticulture_assistant.sensor_validation import (
    collate_issue_messages,
    validate_sensor_links,
)

sensor_validation = sys.modules["custom_components.horticulture_assistant.sensor_validation"]


class DummyStates:
    def __init__(self, states: dict[str, object]) -> None:
        self._states = states

    def get(self, entity_id: str) -> object | None:
        return self._states.get(entity_id)


class DummyState:
    def __init__(self, **attrs: object) -> None:
        self.attributes = attrs


@pytest.mark.parametrize(
    "unit",
    ["Lux", "lux", "klx", "kilolux"],
)
def test_validate_sensor_links_accepts_illuminance_variants(unit):
    hass = types.SimpleNamespace(
        states=DummyStates(
            {
                "sensor.light": DummyState(device_class="illuminance", unit_of_measurement=unit),
            }
        )
    )
    result = validate_sensor_links(hass, {"illuminance": "sensor.light"})
    assert not result.errors
    assert not result.warnings


def test_validate_sensor_links_accepts_conductivity_variants():
    hass = types.SimpleNamespace(
        states=DummyStates(
            {
                "sensor.ec": DummyState(device_class="conductivity", unit_of_measurement="dS/m"),
                "sensor.ec2": DummyState(device_class="conductivity", unit_of_measurement="µS/cm"),
            }
        )
    )
    result = validate_sensor_links(
        hass,
        {
            "ec": "sensor.ec",
        },
    )
    assert result.errors == []
    assert result.warnings == []


def test_validate_sensor_links_missing_entity_reports_error():
    hass = types.SimpleNamespace(states=DummyStates({}))
    result = validate_sensor_links(hass, {"temperature": "sensor.missing"})
    assert len(result.errors) == 1
    summary = collate_issue_messages(result.errors)
    assert "missing_entity" in summary


class FakeTempUnit(Enum):
    CELSIUS = "°C"


def test_validate_sensor_links_accepts_enum_units(monkeypatch):
    monkeypatch.setitem(sensor_validation.EXPECTED_UNITS, "temperature", {FakeTempUnit.CELSIUS})
    hass = types.SimpleNamespace(
        states=DummyStates(
            {
                "sensor.temp": DummyState(
                    device_class="temperature",
                    unit_of_measurement=FakeTempUnit.CELSIUS,
                )
            }
        )
    )

    result = validate_sensor_links(hass, {"temperature": "sensor.temp"})

    assert result.errors == []
    assert result.warnings == []
