from __future__ import annotations

from datetime import UTC, datetime

import pytest

from custom_components.horticulture_assistant.profile_monitor import ProfileMonitor
from custom_components.horticulture_assistant.utils.entry_helpers import ProfileContext


class DummyState:
    def __init__(
        self,
        state: str,
        *,
        unit: str | None = None,
        changed: datetime | None = None,
    ) -> None:
        self.state = state
        self.attributes = {"unit_of_measurement": unit} if unit else {}
        self.last_changed = changed
        self.last_updated = changed


class DummyStates:
    def __init__(self, mapping: dict[str, DummyState]) -> None:
        self._mapping = mapping

    def get(self, entity_id: str) -> DummyState | None:
        return self._mapping.get(entity_id)


class DummyHass:
    def __init__(self, states: DummyStates) -> None:
        self.states = states


def _context(**kwargs) -> ProfileContext:
    payload = {
        "id": "plant",
        "name": "Plant",
        "sensors": {"temperature": ("sensor.temp",), "moisture": ("sensor.moisture",)},
    }
    payload.update(kwargs)
    return ProfileContext(**payload)


def test_profile_monitor_reports_ok() -> None:
    changed = datetime(2024, 1, 1, tzinfo=UTC)
    hass = DummyHass(
        DummyStates(
            {
                "sensor.temp": DummyState("22.3", unit="°C", changed=changed),
                "sensor.moisture": DummyState("45", unit="%", changed=changed),
            }
        )
    )
    context = _context(thresholds={"temperature_max": 28, "moisture_min": 30})
    result = ProfileMonitor(hass, context).evaluate()

    assert result.health == "ok"
    assert result.issues == ()
    assert result.last_sample_at == changed
    attrs = result.as_attributes()
    assert attrs["sensor_count"] == 2
    assert attrs["health"] == "ok"


def test_profile_monitor_flags_missing_sensor() -> None:
    hass = DummyHass(DummyStates({}))
    context = _context(sensors={"moisture": ("sensor.missing",)})

    result = ProfileMonitor(hass, context).evaluate()

    assert result.health == "attention"
    attention = result.issues_for("attention")
    assert len(attention) == 1
    assert attention[0].summary == "sensor_missing"


def test_profile_monitor_flags_out_of_range() -> None:
    changed = datetime(2024, 5, 1, tzinfo=UTC)
    hass = DummyHass(DummyStates({"sensor.moisture": DummyState("10", changed=changed)}))
    context = _context(sensors={"moisture": ("sensor.moisture",)}, thresholds={"moisture_min": 30})

    result = ProfileMonitor(hass, context).evaluate()

    assert result.health == "problem"
    problems = result.issues_for("problem")
    assert len(problems) == 1
    assert problems[0].summary == "sensor_below_minimum"
    assert result.last_sample_at == changed


def test_profile_monitor_threshold_parses_strings_with_units() -> None:
    hass = DummyHass(
        DummyStates(
            {
                "sensor.moisture": DummyState("25"),
            }
        )
    )
    context = _context(
        sensors={"moisture": ("sensor.moisture",)},
        thresholds={"moisture_min": "30 %"},
    )

    result = ProfileMonitor(hass, context).evaluate()

    assert result.health == "problem"
    problems = result.issues_for("problem")
    assert problems and problems[0].summary == "sensor_below_minimum"


@pytest.mark.parametrize(
    "state, expected",
    [
        ("abc", "attention"),
        ("100", "problem"),
    ],
)
def test_profile_monitor_handles_non_numeric_and_high(state: str, expected: str) -> None:
    hass = DummyHass(DummyStates({"sensor.temp": DummyState(state)}))
    context = _context(sensors={"temperature": ("sensor.temp",)}, thresholds={"temperature_max": 80})

    result = ProfileMonitor(hass, context).evaluate()
    assert result.health == expected


def test_profile_monitor_preserves_last_changed_and_updated() -> None:
    changed = datetime(2024, 6, 1, 12, tzinfo=UTC)
    updated = datetime(2024, 6, 1, 13, tzinfo=UTC)
    state = DummyState("42", changed=changed)
    state.last_updated = updated
    hass = DummyHass(DummyStates({"sensor.temp": state}))
    context = _context(sensors={"temperature": ("sensor.temp",)})

    result = ProfileMonitor(hass, context).evaluate()

    assert result.last_sample_at == updated
    snapshot = result.sensors[0]
    assert snapshot.last_changed == changed
    assert snapshot.last_updated == updated
