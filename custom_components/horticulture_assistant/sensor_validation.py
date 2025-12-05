"""Helpers for validating sensor entity assignments."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import Enum, StrEnum
from typing import TYPE_CHECKING, Any

try:  # pragma: no cover - fallback for tests without Home Assistant
    from homeassistant import const as ha_const
except ModuleNotFoundError:  # pragma: no cover - executed in stubbed env
    import types

    ha_const = types.SimpleNamespace(  # type: ignore[assignment]
        CONCENTRATION_PARTS_PER_MILLION="ppm",
        LIGHT_LUX="lx",
        PERCENTAGE="%",
        UnitOfTemperature=types.SimpleNamespace(CELSIUS="°C", FAHRENHEIT="°F"),
    )

try:  # pragma: no cover - fallback for tests
    from homeassistant.components.sensor import SensorDeviceClass
except ModuleNotFoundError:  # pragma: no cover - executed in stubbed env

    class SensorDeviceClass(StrEnum):
        TEMPERATURE = "temperature"
        HUMIDITY = "humidity"
        ILLUMINANCE = "illuminance"
        MOISTURE = "moisture"
        CO2 = "co2"
        CONDUCTIVITY = "conductivity"
        BATTERY = "battery"


if TYPE_CHECKING:  # pragma: no cover - typing only
    from homeassistant.core import HomeAssistant
else:
    HomeAssistant = Any  # type: ignore[assignment]


@dataclass(slots=True)
class SensorValidationIssue:
    """Represents a validation error or warning for a linked sensor."""

    role: str
    entity_id: str
    issue: str
    severity: str
    expected: str | None = None
    observed: str | None = None


@dataclass(slots=True)
class SensorValidationResult:
    """Result of validating a collection of sensor links."""

    errors: list[SensorValidationIssue]
    warnings: list[SensorValidationIssue]


EXPECTED_DEVICE_CLASSES: dict[str, SensorDeviceClass] = {
    "temperature": SensorDeviceClass.TEMPERATURE,
    "soil_temperature": SensorDeviceClass.TEMPERATURE,
    "humidity": SensorDeviceClass.HUMIDITY,
    "illuminance": SensorDeviceClass.ILLUMINANCE,
    "moisture": SensorDeviceClass.MOISTURE,
    "co2": SensorDeviceClass.CO2,
    "ec": SensorDeviceClass.CONDUCTIVITY,
    "conductivity": SensorDeviceClass.CONDUCTIVITY,
    "battery": SensorDeviceClass.BATTERY,
}


_CO2_UNITS: set[str] = {"ppm"}
_CO2_CONSTANT = getattr(ha_const, "CONCENTRATION_PARTS_PER_MILLION", None)
if isinstance(_CO2_CONSTANT, str):
    _CO2_UNITS.add(_CO2_CONSTANT)


_LIGHT_LUX = getattr(ha_const, "LIGHT_LUX", "lx")
_PERCENTAGE = getattr(ha_const, "PERCENTAGE", "%")
_UnitOfTemperature = getattr(ha_const, "UnitOfTemperature", None)

if _UnitOfTemperature is not None:
    _TEMPERATURE_UNITS: set[Any] = {
        _UnitOfTemperature.CELSIUS,
        _UnitOfTemperature.FAHRENHEIT,
    }
else:
    _TEMPERATURE_UNITS = {
        "°c",
        "c",
        "celsius",
        "degc",
        "°f",
        "f",
        "fahrenheit",
        "degf",
    }

EXPECTED_UNITS: dict[str, set[Any]] = {
    "temperature": _TEMPERATURE_UNITS,
    "soil_temperature": _TEMPERATURE_UNITS,
    "humidity": {_PERCENTAGE, "%", "percent"},
    "moisture": {_PERCENTAGE, "%", "percent"},
    "illuminance": {_LIGHT_LUX, "lx", "lux", "klx", "kilolux"},
    "co2": _CO2_UNITS,
    "ec": {"µS/cm", "uS/cm", "us/cm", "mS/cm", "ds/m", "s/m"},
    "conductivity": {"µs/cm", "us/cm", "ms/cm", "ds/m", "s/m"},
    "battery": {_PERCENTAGE, "%", "percent"},
}


def _normalise_device_class(value: str | None) -> str | None:
    if value is None:
        return None
    return str(value).lower()


def _normalise_unit(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, Enum):
        value = value.value
    # Normalise similar Unicode characters so unit comparisons remain reliable.
    # Home Assistant core typically uses the micro sign (``µ``), but a number of
    # integrations report the Greek mu character (``μ``) instead.  Treat them as
    # equivalent to avoid false-positive warnings when validating conductivity
    # sensors.  Perform the replacements before lower-casing to preserve the
    # canonical symbol in the stored unit string.
    text = str(value).replace("º", "°").replace("μ", "µ").strip()
    if not text:
        return None
    return text.lower()


def _iter_sensor_entities(value: Any) -> list[str]:
    """Return a list of cleaned entity ids for ``value``."""

    if isinstance(value, str):
        entity_id = value.strip()
        return [entity_id] if entity_id else []
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        entities: list[str] = []
        for item in value:
            if isinstance(item, str):
                candidate = item.strip()
            elif item is None:
                candidate = ""
            else:
                candidate = str(item).strip()
            if candidate:
                entities.append(candidate)
        return entities
    if value is None:
        return []
    entity_id = str(value).strip()
    return [entity_id] if entity_id else []


def validate_sensor_links(hass: HomeAssistant, sensors: Mapping[str, str | Sequence[Any]]) -> SensorValidationResult:
    """Validate a mapping of measurement role to entity ids."""

    errors: list[SensorValidationIssue] = []
    warnings: list[SensorValidationIssue] = []

    for role, raw_value in sensors.items():
        for entity_id in _iter_sensor_entities(raw_value):
            state = hass.states.get(entity_id)
            if state is None:
                errors.append(
                    SensorValidationIssue(
                        role=role,
                        entity_id=entity_id,
                        issue="missing_entity",
                        severity="error",
                    )
                )
                continue

            attributes = state.attributes
            expected_class = EXPECTED_DEVICE_CLASSES.get(role)
            actual_class = _normalise_device_class(attributes.get("device_class"))
            expected_class_name = expected_class.value if expected_class is not None else None
            if expected_class_name and actual_class not in {
                expected_class_name,
                _normalise_device_class(expected_class_name),
            }:
                warnings.append(
                    SensorValidationIssue(
                        role=role,
                        entity_id=entity_id,
                        issue="unexpected_device_class",
                        severity="warning",
                        expected=expected_class_name,
                        observed=actual_class,
                    )
                )

            unit = _normalise_unit(attributes.get("unit_of_measurement"))
            expected_units = {_normalise_unit(unit) for unit in EXPECTED_UNITS.get(role, set())}
            if expected_units and unit and unit not in expected_units:
                warnings.append(
                    SensorValidationIssue(
                        role=role,
                        entity_id=entity_id,
                        issue="unexpected_unit",
                        severity="warning",
                        expected=", ".join(sorted(filter(None, expected_units))),
                        observed=unit,
                    )
                )
            if not unit and role in EXPECTED_UNITS:
                warnings.append(
                    SensorValidationIssue(
                        role=role,
                        entity_id=entity_id,
                        issue="missing_unit",
                        severity="warning",
                    )
                )

    return SensorValidationResult(errors=errors, warnings=warnings)


def collate_issue_messages(issues: Iterable[SensorValidationIssue]) -> str:
    """Return a human friendly summary for diagnostics and notifications."""

    parts: list[str] = []
    for issue in issues:
        message = f"{issue.role} -> {issue.entity_id}: {issue.issue}"
        if issue.expected or issue.observed:
            message += f" (expected {issue.expected or 'n/a'}, observed {issue.observed or 'n/a'})"
        parts.append(message)
    return "\n".join(parts)


__all__ = ["SensorValidationIssue", "SensorValidationResult", "validate_sensor_links", "collate_issue_messages"]
