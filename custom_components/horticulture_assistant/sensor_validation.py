"""Helpers for validating sensor entity assignments."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from homeassistant import const as ha_const
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import LIGHT_LUX, PERCENTAGE, UnitOfTemperature
from homeassistant.core import HomeAssistant


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
    "humidity": SensorDeviceClass.HUMIDITY,
    "illuminance": SensorDeviceClass.ILLUMINANCE,
    "moisture": SensorDeviceClass.MOISTURE,
    "co2": SensorDeviceClass.CO2,
    "ec": SensorDeviceClass.CONDUCTIVITY,
}


_CO2_UNITS: set[str] = {"ppm"}
_CO2_CONSTANT = getattr(ha_const, "CONCENTRATION_PARTS_PER_MILLION", None)
if isinstance(_CO2_CONSTANT, str):
    _CO2_UNITS.add(_CO2_CONSTANT)


EXPECTED_UNITS: dict[str, set[str]] = {
    "temperature": {UnitOfTemperature.CELSIUS, UnitOfTemperature.FAHRENHEIT},
    "humidity": {PERCENTAGE},
    "moisture": {PERCENTAGE},
    "illuminance": {LIGHT_LUX, "lx", "lux", "klx", "kilolux"},
    "co2": _CO2_UNITS,
    "ec": {"µS/cm", "uS/cm", "us/cm", "mS/cm", "ds/m", "s/m"},
}


def _normalise_device_class(value: str | None) -> str | None:
    if value is None:
        return None
    return str(value).lower()


def _normalise_unit(value: str | None) -> str | None:
    if value is None:
        return None
    return str(value).replace("º", "°").strip().lower()


def validate_sensor_links(hass: HomeAssistant, sensors: dict[str, str]) -> SensorValidationResult:
    """Validate a mapping of measurement role to entity id."""

    errors: list[SensorValidationIssue] = []
    warnings: list[SensorValidationIssue] = []

    for role, entity_id in sensors.items():
        if not entity_id:
            continue
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
