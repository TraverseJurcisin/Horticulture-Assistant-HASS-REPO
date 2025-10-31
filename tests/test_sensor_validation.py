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
        state: str = "0",
        last_changed: datetime | None = None,
        last_updated: datetime | None = None,
        **attrs: object,
    ) -> None:
        self.state = state
        if "state_class" not in attrs:
            attrs["state_class"] = "measurement"
        self.attributes = attrs
        now = datetime.now(datetime.UTC)
        self.last_changed = last_changed or now
        self.last_updated = last_updated or last_changed or now


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
    assert "sensor.missing" in summary
    assert "could not be found" in summary


def test_validate_sensor_links_reports_disabled_registry_entity(monkeypatch):
    hass = types.SimpleNamespace(states=DummyStates({}))

    class DummyRegistryEntry:
        disabled_by = "user"

    class DummyRegistry:
        def async_get(self, entity_id: str):
            return DummyRegistryEntry() if entity_id == "sensor.temp" else None

    monkeypatch.setattr(
        sensor_validation,
        "er",
        types.SimpleNamespace(async_get=lambda _hass: DummyRegistry()),
    )

    result = sensor_validation.validate_sensor_links(hass, {"temperature": "sensor.temp"})

    assert [issue.issue for issue in result.errors] == ["entity_disabled"]


def test_validate_sensor_links_rejects_non_sensor_domain():
    hass = types.SimpleNamespace(states=DummyStates({"light.kitchen": DummyState(device_class="light")}))

    result = sensor_validation.validate_sensor_links(
        hass,
        {"temperature": "light.kitchen"},
    )

    assert [issue.issue for issue in result.errors] == ["invalid_sensor_domain"]


def test_validate_sensor_links_deduplicates_entities():
    hass = types.SimpleNamespace(states=DummyStates({}))
    result = sensor_validation.validate_sensor_links(
        hass,
        {"temperature": [" sensor.duplicate ", "sensor.duplicate", "sensor.duplicate"]},
    )

    assert len(result.errors) == 1
    assert result.errors[0].entity_id == "sensor.duplicate"


def test_validate_sensor_links_normalises_entity_ids():
    hass = types.SimpleNamespace(
        states=DummyStates(
            {
                "sensor.humidity": DummyState(device_class="humidity", unit_of_measurement="%"),
            }
        )
    )

    result = sensor_validation.validate_sensor_links(
        hass,
        {"humidity": [" SENSOR.HUMIDITY ", "sensor.humidity"]},
    )

    assert not result.errors
    assert not result.warnings


def test_validate_sensor_links_uses_original_device_class_when_missing_device_class():
    hass = types.SimpleNamespace(
        states=DummyStates(
            {
                "sensor.moisture": DummyState(
                    original_device_class="moisture",
                    unit_of_measurement="%",
                ),
            }
        )
    )

    result = sensor_validation.validate_sensor_links(
        hass,
        {"moisture": "sensor.moisture"},
    )

    assert not result.errors
    assert not result.warnings


def test_validate_sensor_links_warns_when_device_class_missing():
    hass = types.SimpleNamespace(
        states=DummyStates(
            {
                "sensor.temp": DummyState(unit_of_measurement="°C"),
            }
        )
    )

    result = sensor_validation.validate_sensor_links(
        hass,
        {"temperature": "sensor.temp"},
    )

    assert [issue.issue for issue in result.warnings] == ["missing_device_class"]
    warning = result.warnings[0]
    assert warning.expected == "temperature"
    summary = sensor_validation.collate_issue_messages(result.warnings)
    assert "missing a device class" in summary.lower()


def test_validate_sensor_links_warns_on_unexpected_device_class():
    hass = types.SimpleNamespace(
        states=DummyStates(
            {
                "sensor.temp": DummyState(
                    device_class="humidity",
                    unit_of_measurement="°C",
                ),
            }
        )
    )

    result = sensor_validation.validate_sensor_links(
        hass,
        {"temperature": "sensor.temp"},
    )

    assert [issue.issue for issue in result.warnings] == ["unexpected_device_class"]
    warning = result.warnings[0]
    assert warning.expected == "temperature"
    assert warning.observed == "humidity"


def test_validate_sensor_links_uses_entity_registry_metadata(monkeypatch):
    hass = types.SimpleNamespace(
        states=DummyStates(
            {
                "sensor.temp": types.SimpleNamespace(state="21", attributes={}),
            }
        )
    )

    class DummyRegistryEntry:
        device_class = sensor_validation.SensorDeviceClass.TEMPERATURE
        original_device_class = None
        unit_of_measurement = "°C"
        capabilities = {"state_class": "measurement"}

    class DummyRegistry:
        def async_get(self, entity_id: str) -> DummyRegistryEntry | None:
            return DummyRegistryEntry() if entity_id == "sensor.temp" else None

    monkeypatch.setattr(
        sensor_validation,
        "er",
        types.SimpleNamespace(async_get=lambda _hass: DummyRegistry()),
    )

    result = sensor_validation.validate_sensor_links(
        hass,
        {"temperature": "sensor.temp"},
    )

    assert result.errors == []
    assert result.warnings == []


def test_validate_sensor_links_accepts_enum_device_class_value():
    hass = types.SimpleNamespace(
        states=DummyStates(
            {
                "sensor.temp": DummyState(
                    device_class=sensor_validation.SensorDeviceClass.TEMPERATURE,
                    unit_of_measurement="°C",
                ),
            }
        )
    )

    result = sensor_validation.validate_sensor_links(
        hass,
        {"temperature": "sensor.temp"},
    )

    assert result.errors == []
    assert result.warnings == []


def test_iter_sensor_entities_skips_blank_items():
    assert sensor_validation._iter_sensor_entities([" ", None, "  "]) == []
    assert sensor_validation._iter_sensor_entities("   ") == []


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


def test_validate_sensor_links_accepts_expected_state_class():
    hass = types.SimpleNamespace(
        states=DummyStates(
            {
                "sensor.temp": DummyState(
                    device_class="temperature",
                    unit_of_measurement="°C",
                    state_class="measurement",
                ),
            }
        )
    )

    result = sensor_validation.validate_sensor_links(hass, {"temperature": "sensor.temp"})

    assert not result.errors
    assert not result.warnings


def test_collate_issue_messages_describes_missing_unit_expectations():
    hass = types.SimpleNamespace(
        states=DummyStates(
            {
                "sensor.temp": DummyState(device_class="temperature"),
            }
        )
    )

    result = sensor_validation.validate_sensor_links(hass, {"temperature": "sensor.temp"})
    assert not result.errors
    assert len(result.warnings) == 1

    summary = sensor_validation.collate_issue_messages(result.warnings)
    assert "Provide" in summary
    assert "sensor.temp" in summary
    assert "°C" in summary
    assert "°F" in summary


def test_collate_issue_messages_highlights_disabled_entities():
    issue = sensor_validation.SensorValidationIssue(
        role="moisture",
        entity_id="sensor.moisture",
        issue="entity_disabled",
        severity="error",
        observed="integration",
    )

    summary = sensor_validation.collate_issue_messages([issue])
    assert "is disabled" in summary
    assert "integration" in summary


def test_validate_sensor_links_warns_when_state_class_missing():
    hass = types.SimpleNamespace(
        states=DummyStates(
            {
                "sensor.temp": DummyState(
                    device_class="temperature",
                    unit_of_measurement="°C",
                    state_class=None,
                ),
            }
        )
    )

    result = sensor_validation.validate_sensor_links(hass, {"temperature": "sensor.temp"})

    assert not result.errors
    assert len(result.warnings) == 1
    warning = result.warnings[0]
    assert warning.issue == "missing_state_class"
    assert warning.expected == "measurement"

    summary = sensor_validation.collate_issue_messages(result.warnings)
    assert "state class" in summary
    assert "measurement" in summary


def test_validate_sensor_links_reports_canonical_unit_labels_for_unexpected_unit():
    hass = types.SimpleNamespace(
        states=DummyStates(
            {
                "sensor.temp": DummyState(
                    device_class="temperature",
                    unit_of_measurement="Kelvin",
                ),
            }
        )
    )

    result = sensor_validation.validate_sensor_links(
        hass,
        {"temperature": "sensor.temp"},
    )

    assert not result.errors
    assert len(result.warnings) == 1
    warning = result.warnings[0]
    assert warning.issue == "unexpected_unit"
    assert warning.expected == "°C, °F"
    assert warning.observed == "Kelvin"

    summary = sensor_validation.collate_issue_messages(result.warnings)
    assert "Kelvin" in summary
    assert "°C" in summary
    assert "°F" in summary


def test_validate_sensor_links_warns_on_unexpected_state_class():
    hass = types.SimpleNamespace(
        states=DummyStates(
            {
                "sensor.temp": DummyState(
                    device_class="temperature",
                    unit_of_measurement="°C",
                    state_class="total",
                ),
            }
        )
    )

    result = sensor_validation.validate_sensor_links(hass, {"temperature": "sensor.temp"})

    assert not result.errors
    assert len(result.warnings) == 1
    warning = result.warnings[0]
    assert warning.issue == "unexpected_state_class"
    assert warning.expected == "measurement"
    assert warning.observed == "total"

    summary = sensor_validation.collate_issue_messages(result.warnings)
    assert "state class" in summary
    assert "total" in summary


def test_validate_sensor_links_uses_native_unit_when_unit_of_measurement_missing():
    hass = types.SimpleNamespace(
        states=DummyStates(
            {
                "sensor.temp_native": DummyState(
                    device_class="temperature",
                    native_unit_of_measurement="°C",
                ),
            }
        )
    )

    result = sensor_validation.validate_sensor_links(
        hass,
        {"temperature": "sensor.temp_native"},
    )

    assert not result.errors
    assert not result.warnings


def test_validate_sensor_links_uses_suggested_display_unit_as_last_resort():
    hass = types.SimpleNamespace(
        states=DummyStates(
            {
                "sensor.light": DummyState(
                    device_class="illuminance",
                    suggested_display_unit="lux",
                ),
            }
        )
    )

    result = sensor_validation.validate_sensor_links(
        hass,
        {"illuminance": "sensor.light"},
    )

    assert not result.errors
    assert not result.warnings


def test_validate_sensor_links_uses_original_unit_when_only_original_present():
    hass = types.SimpleNamespace(
        states=DummyStates(
            {
                "sensor.light": DummyState(
                    device_class="illuminance",
                    original_unit_of_measurement="lux",
                ),
            }
        )
    )

    result = sensor_validation.validate_sensor_links(
        hass,
        {"illuminance": "sensor.light"},
    )

    assert not result.errors
    assert not result.warnings


@pytest.mark.parametrize("state", ["unknown", "unavailable", "Unavailable", " UNKNOWN "])
def test_validate_sensor_links_warns_when_sensor_unavailable(state):
    hass = types.SimpleNamespace(
        states=DummyStates(
            {
                "sensor.temp": DummyState(
                    state=state,
                    device_class="temperature",
                    unit_of_measurement="°C",
                ),
            }
        )
    )

    result = sensor_validation.validate_sensor_links(
        hass,
        {"temperature": "sensor.temp"},
    )

    assert not result.errors
    assert len(result.warnings) == 1
    warning = result.warnings[0]
    assert warning.issue == "unavailable_state"

    summary = sensor_validation.collate_issue_messages(result.warnings)
    assert "sensor.temp" in summary
    assert "unavailable" in summary or "hasn't reported" in summary


def test_validate_sensor_links_warns_when_state_not_numeric():
    hass = types.SimpleNamespace(
        states=DummyStates(
            {
                "sensor.temp": DummyState(
                    state="high",
                    device_class="temperature",
                    unit_of_measurement="°C",
                ),
            }
        )
    )

    result = sensor_validation.validate_sensor_links(
        hass,
        {"temperature": "sensor.temp"},
    )

    assert not result.errors
    assert [warning.issue for warning in result.warnings] == ["non_numeric_state"]

    summary = sensor_validation.collate_issue_messages(result.warnings)
    assert "non-numeric" in summary
    assert "sensor.temp" in summary


@pytest.mark.parametrize("raw_state", [None, "  "])
def test_validate_sensor_links_warns_when_state_empty(raw_state):
    hass = types.SimpleNamespace(
        states=DummyStates(
            {
                "sensor.temp": DummyState(
                    state=raw_state,
                    device_class="temperature",
                    unit_of_measurement="°C",
                ),
            }
        )
    )

    result = sensor_validation.validate_sensor_links(
        hass,
        {"temperature": "sensor.temp"},
    )

    assert not result.errors
    assert [warning.issue for warning in result.warnings] == ["empty_state"]

    summary = sensor_validation.collate_issue_messages(result.warnings)
    assert "hasn't reported a value yet" in summary
    assert "sensor.temp" in summary


def test_validate_sensor_links_flags_boolean_states():
    hass = types.SimpleNamespace(
        states=DummyStates(
            {
                "sensor.temp": DummyState(
                    state=True,
                    device_class="temperature",
                    unit_of_measurement="°C",
                ),
            }
        )
    )

    result = sensor_validation.validate_sensor_links(
        hass,
        {"temperature": "sensor.temp"},
    )

    assert not result.errors
    assert [warning.issue for warning in result.warnings] == ["non_numeric_state"]

    summary = sensor_validation.collate_issue_messages(result.warnings)
    assert "sensor.temp" in summary
    assert "non-numeric" in summary


def test_validate_sensor_links_warns_on_stale_state(monkeypatch):
    now = datetime(2024, 1, 1, 12, 0, tzinfo=datetime.UTC)
    stale = now - timedelta(hours=3, minutes=5)
    hass = types.SimpleNamespace(
        states=DummyStates(
            {
                "sensor.temp": DummyState(
                    state="12",
                    device_class="temperature",
                    unit_of_measurement="°C",
                    last_changed=stale,
                    last_updated=stale,
                ),
            }
        )
    )

    monkeypatch.setattr(sensor_validation.dt_util, "utcnow", lambda: now)

    result = sensor_validation.validate_sensor_links(
        hass,
        {"temperature": "sensor.temp"},
    )

    assert [warning.issue for warning in result.warnings] == ["stale_state"]
    warning = result.warnings[0]
    assert warning.expected == "1 hour"
    assert warning.observed == "3 hours 5 minutes"
    summary = sensor_validation.collate_issue_messages(result.warnings)
    assert "hasn't updated in over" in summary
    assert "3 hours 5 minutes" in summary


def test_validate_sensor_links_uses_custom_stale_threshold(monkeypatch):
    now = datetime(2024, 1, 1, 12, 0, tzinfo=datetime.UTC)
    stale = now - timedelta(hours=5)
    hass = types.SimpleNamespace(
        states=DummyStates(
            {
                "sensor.temp": DummyState(
                    state="12",
                    device_class="temperature",
                    unit_of_measurement="°C",
                    last_changed=stale,
                    last_updated=stale,
                ),
            }
        )
    )

    monkeypatch.setattr(sensor_validation.dt_util, "utcnow", lambda: now)

    result = sensor_validation.validate_sensor_links(
        hass,
        {"temperature": "sensor.temp"},
        stale_after=timedelta(hours=4),
    )

    assert [warning.issue for warning in result.warnings] == ["stale_state"]
    warning = result.warnings[0]
    assert warning.expected == "4 hours"


def test_recommended_stale_after_defaults_to_hour():
    default = sensor_validation.recommended_stale_after(None)
    assert default == timedelta(hours=1)
    assert sensor_validation.recommended_stale_after(0) == default
    assert sensor_validation.recommended_stale_after("") == default


def test_recommended_stale_after_scales_with_interval():
    default = sensor_validation.recommended_stale_after(None)
    assert sensor_validation.recommended_stale_after(5) == default
    assert sensor_validation.recommended_stale_after(120) == timedelta(hours=6)
    assert sensor_validation.recommended_stale_after(90) == timedelta(hours=4, minutes=30)
    assert sensor_validation.recommended_stale_after("180") == timedelta(hours=9)


def test_recommended_stale_after_parses_extended_formats():
    default = sensor_validation.recommended_stale_after(None)
    assert sensor_validation.recommended_stale_after("PT2H") == timedelta(hours=6)
    assert sensor_validation.recommended_stale_after("01:30:00") == timedelta(hours=4, minutes=30)
    assert sensor_validation.recommended_stale_after("90m") == timedelta(hours=4, minutes=30)
    assert sensor_validation.recommended_stale_after(timedelta(minutes=150)) == timedelta(hours=7, minutes=30)
    assert sensor_validation.recommended_stale_after("bogus") == default


def test_validate_sensor_links_allows_recent_state(monkeypatch):
    now = datetime(2024, 1, 1, 12, 0, tzinfo=datetime.UTC)
    recent = now - timedelta(minutes=15)
    hass = types.SimpleNamespace(
        states=DummyStates(
            {
                "sensor.temp": DummyState(
                    state="12",
                    device_class="temperature",
                    unit_of_measurement="°C",
                    last_changed=recent,
                    last_updated=recent,
                ),
            }
        )
    )

    monkeypatch.setattr(sensor_validation.dt_util, "utcnow", lambda: now)

    result = sensor_validation.validate_sensor_links(
        hass,
        {"temperature": "sensor.temp"},
    )

    assert result.warnings == []


@pytest.mark.parametrize("state", ["unknown", "unavailable"])
def test_validate_sensor_links_skips_missing_unit_warning_for_unavailable_sensor(state):
    hass = types.SimpleNamespace(
        states=DummyStates(
            {
                "sensor.temp": DummyState(
                    state=state,
                    device_class="temperature",
                ),
            }
        )
    )

    result = sensor_validation.validate_sensor_links(
        hass,
        {"temperature": "sensor.temp"},
    )

    assert not result.errors
    assert [warning.issue for warning in result.warnings] == ["unavailable_state"]


def test_format_sensor_issue_distinguishes_unknown_state():
    issue = sensor_validation.SensorValidationIssue(
        role="temperature",
        entity_id="sensor.temp",
        issue="unavailable_state",
        severity="warning",
        observed="unknown",
    )

    summary = sensor_validation.collate_issue_messages([issue])
    assert "hasn't reported" in summary


def test_format_sensor_issue_explains_invalid_sensor_domain():
    issue = sensor_validation.SensorValidationIssue(
        role="temperature",
        entity_id="light.kitchen",
        issue="invalid_sensor_domain",
        severity="error",
    )

    summary = sensor_validation.collate_issue_messages([issue])
    assert "isn't a sensor" in summary
    assert "Select a sensor entity" in summary


def test_validate_sensor_links_reports_shared_entity_between_roles():
    hass = types.SimpleNamespace(
        states=DummyStates(
            {
                "sensor.shared": DummyState(
                    device_class="humidity",
                    unit_of_measurement="%",
                ),
            }
        )
    )

    result = sensor_validation.validate_sensor_links(
        hass,
        {
            "humidity": "sensor.shared",
            "temperature": "sensor.shared",
        },
    )

    shared = [issue for issue in result.errors if issue.issue == "shared_entity"]
    assert len(shared) == 2
    assert {issue.role for issue in shared} == {"humidity", "temperature"}
    summary = sensor_validation.collate_issue_messages(shared)
    assert "already linked" in summary.lower()
    assert "humidity" in summary.lower()
    assert "temperature" in summary.lower()


def test_collate_issue_messages_lists_other_roles_for_shared_entity():
    issue = sensor_validation.SensorValidationIssue(
        role="temperature",
        entity_id="sensor.shared",
        issue="shared_entity",
        severity="error",
        observed="humidity,co2",
    )

    summary = sensor_validation.collate_issue_messages([issue])
    assert "Humidity" in summary
    assert "Co2" in summary
    assert "choose a dedicated sensor" in summary.lower()
