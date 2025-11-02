import importlib
import sys
import types
from datetime import datetime, timedelta
from enum import Enum

import pytest

import custom_components.horticulture_assistant.sensor_validation as sensor_validation


class DummyStates:
    def __init__(self, states: dict[str, object]) -> None:
        self._states = states

    def get(self, entity_id: str) -> object | None:
        return self._states.get(entity_id)


class DummyState:
    def __init__(
        self,
        *,
        state: object | None = None,
        last_updated: datetime | None = None,
        last_changed: datetime | None = None,
        **attrs: object,
    ) -> None:
        self.attributes = attrs
        self.state = state
        self.last_updated = last_updated
        self.last_changed = last_changed


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
    result = sensor_validation.validate_sensor_links(hass, {"illuminance": "sensor.light"})
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
    result = sensor_validation.validate_sensor_links(
        hass,
        {
            "ec": "sensor.ec",
        },
    )
    assert result.errors == []
    assert result.warnings == []


def test_validate_sensor_links_handles_sequence_inputs():
    hass = types.SimpleNamespace(
        states=DummyStates(
            {
                "sensor.one": DummyState(),
                "sensor.two": DummyState(),
            }
        )
    )

    result = sensor_validation.validate_sensor_links(
        hass,
        {"environment": [" sensor.one ", "sensor.two", None]},
    )

    assert result.errors == []
    assert result.warnings == []


def test_validate_sensor_links_missing_entity_reports_error():
    hass = types.SimpleNamespace(states=DummyStates({}))
    result = sensor_validation.validate_sensor_links(hass, {"temperature": "sensor.missing"})
    assert len(result.errors) == 1
    summary = sensor_validation.collate_issue_messages(result.errors)
    assert "missing_entity" in summary


def test_validate_sensor_links_accepts_temperature_enum_units(monkeypatch):
    class UnitOfTemperature(Enum):
        CELSIUS = "°C"
        FAHRENHEIT = "°F"

    const_module = types.ModuleType("homeassistant.const")
    const_module.CONCENTRATION_PARTS_PER_MILLION = "ppm"
    const_module.LIGHT_LUX = "lx"
    const_module.PERCENTAGE = "%"
    const_module.UnitOfTemperature = UnitOfTemperature

    monkeypatch.setitem(sys.modules, "homeassistant.const", const_module)
    reloaded = importlib.reload(sensor_validation)

    try:
        hass = types.SimpleNamespace(
            states=DummyStates(
                {
                    "sensor.temperature": DummyState(
                        device_class="temperature",
                        unit_of_measurement=UnitOfTemperature.CELSIUS,
                    ),
                }
            )
        )
        result = reloaded.validate_sensor_links(hass, {"temperature": "sensor.temperature"})
        assert result.errors == []
        assert result.warnings == []
    finally:
        monkeypatch.delitem(sys.modules, "homeassistant.const", raising=False)
        monkeypatch.delitem(sys.modules, "homeassistant", raising=False)
        importlib.reload(sensor_validation)


def test_validate_sensor_links_flags_stale_state(monkeypatch):
    now = datetime.now(datetime.UTC)
    stale_time = now - timedelta(hours=2)

    hass = types.SimpleNamespace(
        states=DummyStates(
            {
                "sensor.temp": DummyState(
                    state="21.4",
                    last_updated=stale_time,
                    device_class="temperature",
                    unit_of_measurement="°C",
                )
            }
        )
    )

    class DummyDateTimeModule:
        @staticmethod
        def utcnow() -> datetime:
            return now

    monkeypatch.setattr(sensor_validation, "dt_util", DummyDateTimeModule())

    result = sensor_validation.validate_sensor_links(
        hass,
        {"temperature": "sensor.temp"},
        stale_after=timedelta(minutes=30),
    )

    assert not result.errors
    assert len(result.warnings) == 1
    issue = result.warnings[0]
    assert issue.issue == "stale_state"
    assert issue.expected
    assert issue.observed


def test_recommended_stale_after_scales_with_interval():
    default = sensor_validation.recommended_stale_after(None)
    assert default == timedelta(hours=1)

    long_interval = sensor_validation.recommended_stale_after(30)
    assert long_interval == timedelta(minutes=90)

    iso = sensor_validation.recommended_stale_after("PT10M")
    assert iso == default

    clock = sensor_validation.recommended_stale_after("00:45")
    assert clock == timedelta(hours=2, minutes=15)
