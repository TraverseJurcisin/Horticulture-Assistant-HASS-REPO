import types

import pytest

from custom_components.horticulture_assistant.sensor_validation import (
    collate_issue_messages,
    validate_sensor_links,
)


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
