"""Helpers for validating sensor entity assignments."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any

import math
import re
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
    from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
except ModuleNotFoundError:  # pragma: no cover - executed in stubbed env
    from enum import Enum

    class SensorDeviceClass(str, Enum):
        TEMPERATURE = "temperature"
        HUMIDITY = "humidity"
        ILLUMINANCE = "illuminance"
        MOISTURE = "moisture"
        CO2 = "co2"
        CONDUCTIVITY = "conductivity"

    class SensorStateClass(str, Enum):
        MEASUREMENT = "measurement"
        TOTAL = "total"
        TOTAL_INCREASING = "total_increasing"


if TYPE_CHECKING:  # pragma: no cover - typing only
    from homeassistant.core import HomeAssistant
else:
    HomeAssistant = Any  # type: ignore[assignment]

try:  # pragma: no cover - fallback when Home Assistant not installed
    from homeassistant.helpers import entity_registry as er  # type: ignore[attr-defined]
except (ModuleNotFoundError, ImportError):  # pragma: no cover - executed in stubbed env
    er = None  # type: ignore[assignment]


try:  # pragma: no cover - fallback when Home Assistant not installed
    from homeassistant.util import dt as dt_util  # type: ignore[attr-defined]
except (ModuleNotFoundError, ImportError):  # pragma: no cover - executed in stubbed env
    class _FallbackDateTimeModule:  # pragma: no cover - simple fallback for tests
        @staticmethod
        def utcnow() -> datetime:
            return datetime.now(timezone.utc)

    dt_util = _FallbackDateTimeModule()  # type: ignore[assignment]


from .utils.state_helpers import coerce_numeric_value


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


EXPECTED_STATE_CLASSES: dict[str, set[SensorStateClass]] = {
    "temperature": {SensorStateClass.MEASUREMENT},
    "humidity": {SensorStateClass.MEASUREMENT},
    "illuminance": {SensorStateClass.MEASUREMENT},
    "moisture": {SensorStateClass.MEASUREMENT},
    "co2": {SensorStateClass.MEASUREMENT},
    "ec": {SensorStateClass.MEASUREMENT},
}


_CO2_UNITS: set[str] = {"ppm"}
_CO2_CONSTANT = getattr(ha_const, "CONCENTRATION_PARTS_PER_MILLION", None)
if isinstance(_CO2_CONSTANT, str):
    _CO2_UNITS.add(_CO2_CONSTANT)


_LIGHT_LUX = getattr(ha_const, "LIGHT_LUX", "lx")
_PERCENTAGE = getattr(ha_const, "PERCENTAGE", "%")
_UnitOfTemperature = getattr(ha_const, "UnitOfTemperature", None)

_STATE_UNKNOWN = getattr(ha_const, "STATE_UNKNOWN", "unknown")
_STATE_UNAVAILABLE = getattr(ha_const, "STATE_UNAVAILABLE", "unavailable")

if _UnitOfTemperature is not None:
    _TEMPERATURE_UNITS: set[Any] = {
        _UnitOfTemperature.CELSIUS,
        _UnitOfTemperature.FAHRENHEIT,
    }
else:
    _TEMPERATURE_UNITS = {
        "°C",
        "°F",
        "c",
        "celsius",
        "degc",
        "f",
        "fahrenheit",
        "degf",
    }

EXPECTED_UNITS: dict[str, set[Any]] = {
    "temperature": _TEMPERATURE_UNITS,
    "humidity": {_PERCENTAGE, "%", "percent", "percentage"},
    "moisture": {_PERCENTAGE, "%", "percent", "percentage"},
    "illuminance": {_LIGHT_LUX, "lx", "lux", "klx", "kilolux"},
    "co2": _CO2_UNITS,
    "ec": {"µS/cm", "uS/cm", "us/cm", "mS/cm", "ds/m", "s/m"},
}


_UNAVAILABLE_STATES = {
    value
    for value in (
        str(_STATE_UNAVAILABLE).strip().lower(),
        str(_STATE_UNKNOWN).strip().lower(),
    )
    if value
}


_STALE_STATE_THRESHOLD = timedelta(hours=1)


_ISO_DURATION_RE = re.compile(
    r"^p(?:"  # duration always starts with P
    r"(?:(?P<days>\d+(?:\.\d+)?)d)?"  # optional day component
    r"(?:t"  # time component begins with T when present
    r"(?:(?P<hours>\d+(?:\.\d+)?)h)?"
    r"(?:(?P<minutes>\d+(?:\.\d+)?)m)?"
    r"(?:(?P<seconds>\d+(?:\.\d+)?)s)?"
    r")?"
    r")$",
    re.IGNORECASE,
)


_MINUTE_SUFFIXES = {"m", "min", "mins", "minute", "minutes"}


def _coerce_datetime(*values: Any) -> datetime | None:
    """Return the most recent timezone-aware datetime from ``values``."""

    latest: datetime | None = None
    for candidate in values:
        if not isinstance(candidate, datetime):
            continue
        if candidate.tzinfo is None:
            candidate = candidate.replace(tzinfo=timezone.utc)
        else:
            candidate = candidate.astimezone(timezone.utc)
        if latest is None or candidate > latest:
            latest = candidate
    return latest


def _is_stale(last_seen: datetime, threshold: timedelta) -> bool:
    """Return ``True`` if ``last_seen`` is older than ``threshold``."""

    now = dt_util.utcnow()
    if last_seen >= now:
        return False
    return now - last_seen > threshold


def _normalise_stale_after(value: timedelta | None) -> timedelta:
    """Return a positive threshold for stale-state checks."""

    if not isinstance(value, timedelta):
        return _STALE_STATE_THRESHOLD
    if value <= timedelta(0):
        return _STALE_STATE_THRESHOLD
    return value




def _coerce_minutes(value: Any) -> float | None:
    """Return ``value`` expressed in minutes when possible."""

    if isinstance(value, timedelta):
        seconds = value.total_seconds()
        if not math.isfinite(seconds):
            return None
        return seconds / 60

    if isinstance(value, (int, float)):
        minutes = float(value)
        if not math.isfinite(minutes):
            return None
        return minutes

    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None

        lowered = text.lower()
        iso_match = _ISO_DURATION_RE.match(lowered)
        if iso_match:
            days = float(iso_match.group("days") or 0.0)
            hours = float(iso_match.group("hours") or 0.0)
            minutes = float(iso_match.group("minutes") or 0.0)
            seconds = float(iso_match.group("seconds") or 0.0)
            total_minutes = (days * 24 * 60) + (hours * 60) + minutes + (seconds / 60)
            return total_minutes

        if ":" in text:
            parts = text.split(":")
            try:
                if len(parts) == 3:
                    hours, minutes, seconds = (float(part or 0) for part in parts)
                    return hours * 60 + minutes + seconds / 60
                if len(parts) == 2:
                    hours, minutes = (float(part or 0) for part in parts)
                    return hours * 60 + minutes
            except ValueError:
                return None

        number_match = re.match(r"^[+-]?\d+(?:\.\d+)?", lowered)
        if number_match:
            remainder = lowered[number_match.end() :].strip()
            if not remainder or remainder in _MINUTE_SUFFIXES:
                try:
                    return float(number_match.group(0))
                except ValueError:
                    return None

    return None


def recommended_stale_after(update_interval_minutes: float | int | None) -> timedelta:
    """Return a stale warning threshold suited to ``update_interval_minutes``."""

    minutes = _coerce_minutes(update_interval_minutes)
    if minutes is None or minutes <= 0:
        return _STALE_STATE_THRESHOLD
    dynamic = timedelta(minutes=minutes * 3)
    return dynamic if dynamic > _STALE_STATE_THRESHOLD else _STALE_STATE_THRESHOLD


def _format_duration(delta: timedelta) -> str:
    """Return a compact human-readable description of ``delta``."""

    seconds = int(delta.total_seconds())
    if seconds <= 0:
        return "less than a minute"
    minutes = seconds // 60
    if minutes < 1:
        return "less than a minute"
    if minutes < 60:
        return _pluralise(minutes, "minute")
    hours = minutes // 60
    minutes %= 60
    if hours < 24:
        if minutes:
            return f"{_pluralise(hours, 'hour')} {_pluralise(minutes, 'minute')}"
        return _pluralise(hours, "hour")
    days = hours // 24
    hours %= 24
    if days < 7:
        if hours:
            return f"{_pluralise(days, 'day')} {_pluralise(hours, 'hour')}"
        return _pluralise(days, "day")
    weeks = days // 7
    days %= 7
    if days:
        return f"{_pluralise(weeks, 'week')} {_pluralise(days, 'day')}"
    return _pluralise(weeks, "week")


def _pluralise(value: int, word: str) -> str:
    suffix = "s" if value != 1 else ""
    return f"{value} {word}{suffix}"


def _normalise_device_class(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, Enum):
        value = value.value
    elif hasattr(value, "value"):
        candidate = getattr(value, "value")
        if isinstance(candidate, str):
            value = candidate
        elif candidate is not None:
            value = candidate
    text = str(value).strip()
    if not text:
        return None
    return text.lower()


def _format_device_class_label(value: Any) -> str | None:
    """Return a human readable label for ``value``."""

    if value is None:
        return None
    if isinstance(value, Enum):
        value = value.value
    text = str(value).strip()
    return text or None


def _normalise_state_class(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, Enum):
        value = value.value
    text = str(value).strip()
    return text.lower() if text else None


_UNIT_NORMALISATION_OVERRIDES: dict[str, str] = {
    "c": "°c",
    "degc": "°c",
    "celsius": "°c",
    "f": "°f",
    "degf": "°f",
    "fahrenheit": "°f",
    "percent": "%",
    "percentage": "%",
    "us/cm": "µs/cm",
    "kilolux": "klx",
}


_UNIT_LABEL_OVERRIDES: dict[str, str] = {
    "°c": "°C",
    "°f": "°F",
    "%": "%",
    "ppm": "ppm",
    "lx": "lx",
    "lux": "lux",
    "klx": "klx",
    "µs/cm": "µS/cm",
    "ms/cm": "mS/cm",
    "ds/m": "dS/m",
    "s/m": "S/m",
}


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
    lowered = text.casefold()
    return _UNIT_NORMALISATION_OVERRIDES.get(lowered, lowered)


def _format_unit_label(normalised: str | None, raw: Any) -> str | None:
    if normalised is None:
        return None
    override = _UNIT_LABEL_OVERRIDES.get(normalised)
    if override is not None:
        return override
    if isinstance(raw, Enum):
        raw = raw.value
    if raw is None:
        return normalised
    label = str(raw).strip()
    return label or normalised


def _normalise_entity_id(value: Any) -> str | None:
    """Return a lowercase entity id or ``None`` when ``value`` is empty."""

    if value is None:
        return None

    candidate = str(value).strip()
    if not candidate:
        return None

    return candidate.lower()


def _iter_sensor_entities(value: Any) -> list[str]:
    """Return a list of cleaned entity ids for ``value``."""

    def _append_unique(entities: list[str], seen: set[str], candidate: Any) -> None:
        normalised = _normalise_entity_id(candidate)
        if normalised and normalised not in seen:
            entities.append(normalised)
            seen.add(normalised)

    seen: set[str] = set()

    if isinstance(value, str):
        entity_id = _normalise_entity_id(value)
        return [entity_id] if entity_id else []
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        entities: list[str] = []
        for item in value:
            _append_unique(entities, seen, item)
        return entities
    if value is None:
        return []
    entity_id = _normalise_entity_id(value)
    return [entity_id] if entity_id else []


def _resolve_device_class(attributes: Mapping[str, Any]) -> Any:
    """Return the configured device class for ``attributes`` if present."""

    value = attributes.get("device_class")
    if value in (None, ""):
        value = attributes.get("original_device_class")
    return value


def _resolve_unit_of_measurement(attributes: Mapping[str, Any]) -> Any:
    """Return the best available unit of measurement from ``attributes``."""

    for key in (
        "unit_of_measurement",
        "native_unit_of_measurement",
        "suggested_display_unit",
        "suggested_unit_of_measurement",
        "original_unit_of_measurement",
    ):
        if key in attributes:
            value = attributes.get(key)
            if value is None:
                continue
            if isinstance(value, str) and not value.strip():
                continue
            return value
    return None


def validate_sensor_links(
    hass: HomeAssistant,
    sensors: Mapping[str, str | Sequence[Any]],
    *,
    stale_after: timedelta | None = None,
) -> SensorValidationResult:
    """Validate a mapping of measurement role to entity ids."""

    errors: list[SensorValidationIssue] = []
    warnings: list[SensorValidationIssue] = []

    stale_after = _normalise_stale_after(stale_after)

    entity_registry = _get_entity_registry(hass)
    entity_role_map: dict[str, set[str]] = {}

    for role, raw_value in sensors.items():
        for entity_id in _iter_sensor_entities(raw_value):
            registry_entry = None
            if entity_registry is not None:
                try:
                    registry_entry = entity_registry.async_get(entity_id)
                except Exception:  # pragma: no cover - registry lookup best effort
                    registry_entry = None

            state = hass.states.get(entity_id)
            if state is None:
                disabled_by = getattr(registry_entry, "disabled_by", None)
                if disabled_by:
                    errors.append(
                        SensorValidationIssue(
                            role=role,
                            entity_id=entity_id,
                            issue="entity_disabled",
                            severity="error",
                            observed=str(disabled_by),
                        )
                    )
                else:
                    errors.append(
                        SensorValidationIssue(
                            role=role,
                            entity_id=entity_id,
                            issue="missing_entity",
                            severity="error",
                        )
                    )
                continue

            domain = entity_id.split(".", 1)[0] if "." in entity_id else None
            if domain != "sensor":
                errors.append(
                    SensorValidationIssue(
                        role=role,
                        entity_id=entity_id,
                        issue="invalid_sensor_domain",
                        severity="error",
                    )
                )
                continue

            raw_attributes = getattr(state, "attributes", {}) or {}
            if isinstance(raw_attributes, Mapping):
                attributes: Mapping[str, Any] | dict[str, Any] = raw_attributes
            else:
                attributes = dict(getattr(raw_attributes, "items", lambda: [])())

            if registry_entry is not None:
                attributes = _augment_with_registry_attributes(attributes, registry_entry)

            entity_role_map.setdefault(entity_id, set()).add(role)

            raw_state = getattr(state, "state", None)
            observed_state = str(raw_state).strip() if raw_state is not None else ""
            observed_state_lower = observed_state.lower()
            is_unavailable_state = bool(
                observed_state_lower and observed_state_lower in _UNAVAILABLE_STATES
            )
            if is_unavailable_state:
                warnings.append(
                    SensorValidationIssue(
                        role=role,
                        entity_id=entity_id,
                        issue="unavailable_state",
                        severity="warning",
                        observed=observed_state_lower,
                    )
                )
            has_reported_value = bool(observed_state)
            last_updated = _coerce_datetime(
                getattr(state, "last_updated", None), getattr(state, "last_changed", None)
            )
            if (
                has_reported_value
                and not is_unavailable_state
                and last_updated is not None
                and _is_stale(last_updated, stale_after)
            ):
                now = dt_util.utcnow()
                age = now - last_updated
                warnings.append(
                    SensorValidationIssue(
                        role=role,
                        entity_id=entity_id,
                        issue="stale_state",
                        severity="warning",
                        expected=_format_duration(stale_after),
                        observed=_format_duration(age),
                    )
                )
            if not is_unavailable_state:
                if has_reported_value:
                    numeric_value = coerce_numeric_value(raw_state)
                    if numeric_value is None:
                        warnings.append(
                            SensorValidationIssue(
                                role=role,
                                entity_id=entity_id,
                                issue="non_numeric_state",
                                severity="warning",
                                observed=observed_state,
                            )
                        )
                else:
                    warnings.append(
                        SensorValidationIssue(
                            role=role,
                            entity_id=entity_id,
                            issue="empty_state",
                            severity="warning",
                        )
                    )
            expected_class = EXPECTED_DEVICE_CLASSES.get(role)
            raw_device_class = _resolve_device_class(attributes)
            actual_class = _normalise_device_class(raw_device_class)
            expected_class_name = (
                expected_class.value if expected_class is not None else None
            )
            expected_class_normalised = (
                _normalise_device_class(expected_class_name)
                if expected_class_name
                else None
            )
            if expected_class_name and not actual_class:
                warnings.append(
                    SensorValidationIssue(
                        role=role,
                        entity_id=entity_id,
                        issue="missing_device_class",
                        severity="warning",
                        expected=expected_class_name,
                    )
                )
            elif expected_class_normalised and actual_class not in {
                expected_class_normalised
            }:
                observed_label = _format_device_class_label(raw_device_class) or actual_class
                warnings.append(
                    SensorValidationIssue(
                        role=role,
                        entity_id=entity_id,
                        issue="unexpected_device_class",
                        severity="warning",
                        expected=expected_class_name,
                        observed=observed_label,
                    )
                )

            expected_state_classes = EXPECTED_STATE_CLASSES.get(role, set())
            normalised_expected_state_classes: dict[str, str] = {}
            for expected_state_class in expected_state_classes:
                normalised = _normalise_state_class(expected_state_class)
                if not normalised:
                    continue
                if isinstance(expected_state_class, Enum):
                    label = expected_state_class.value
                else:
                    label = str(expected_state_class)
                normalised_expected_state_classes.setdefault(normalised, label)
            observed_state_class_value = attributes.get("state_class")
            observed_state_class = _normalise_state_class(observed_state_class_value)
            if normalised_expected_state_classes and not is_unavailable_state:
                expected_state_class_label = ", ".join(
                    sorted(normalised_expected_state_classes.values(), key=lambda text: text.casefold())
                )
                if not observed_state_class:
                    warnings.append(
                        SensorValidationIssue(
                            role=role,
                            entity_id=entity_id,
                            issue="missing_state_class",
                            severity="warning",
                            expected=expected_state_class_label,
                        )
                    )
                elif observed_state_class not in normalised_expected_state_classes:
                    if isinstance(observed_state_class_value, Enum):
                        observed_state_class_label = observed_state_class_value.value
                    else:
                        observed_state_class_label = str(observed_state_class_value)
                    warnings.append(
                        SensorValidationIssue(
                            role=role,
                            entity_id=entity_id,
                            issue="unexpected_state_class",
                            severity="warning",
                            expected=expected_state_class_label,
                            observed=observed_state_class_label,
                        )
                    )

            raw_unit_value = _resolve_unit_of_measurement(attributes)
            unit = _normalise_unit(raw_unit_value)
            raw_expected_units = EXPECTED_UNITS.get(role, set())
            expected_units_map: dict[str, str] = {}
            for expected in raw_expected_units:
                normalised_expected = _normalise_unit(expected)
                if not normalised_expected:
                    continue
                label = _format_unit_label(normalised_expected, expected) or normalised_expected
                expected_units_map.setdefault(normalised_expected, label)
            expected_units = set(expected_units_map)
            expected_units_label = (
                ", ".join(sorted(expected_units_map.values(), key=lambda text: text.casefold()))
                if expected_units_map
                else None
            )
            observed_unit_label = _format_unit_label(unit, raw_unit_value)
            if expected_units and unit and unit not in expected_units:
                warnings.append(
                    SensorValidationIssue(
                        role=role,
                        entity_id=entity_id,
                        issue="unexpected_unit",
                        severity="warning",
                        expected=expected_units_label,
                        observed=observed_unit_label or unit,
                    )
                )
            if not unit and expected_units and not is_unavailable_state:
                warnings.append(
                    SensorValidationIssue(
                        role=role,
                        entity_id=entity_id,
                        issue="missing_unit",
                        severity="warning",
                        expected=expected_units_label,
                    )
                )

    for entity_id, roles in entity_role_map.items():
        if len(roles) <= 1:
            continue
        sorted_roles = sorted(roles, key=lambda text: text.casefold())
        for role in sorted_roles:
            others = [candidate for candidate in sorted_roles if candidate != role]
            if not others:
                continue
            errors.append(
                SensorValidationIssue(
                    role=role,
                    entity_id=entity_id,
                    issue="shared_entity",
                    severity="error",
                    observed=",".join(others) if others else None,
                )
            )

    return SensorValidationResult(errors=errors, warnings=warnings)


def _format_issue_role(role: str | None) -> str:
    if not role:
        return "Sensor"
    cleaned = str(role).replace("_", " ").strip()
    return cleaned.capitalize() if cleaned else "Sensor"


def _format_role_list(roles: Iterable[str]) -> tuple[str, int]:
    labels = [_format_issue_role(role) for role in roles if role]
    if not labels:
        return "another sensor role", 1
    if len(labels) == 1:
        return labels[0], 1
    if len(labels) == 2:
        return " and ".join(labels), 2
    return f"{', '.join(labels[:-1])}, and {labels[-1]}", len(labels)


def _format_sensor_issue(issue: SensorValidationIssue) -> str:
    severity = issue.severity.upper() if issue.severity else "ISSUE"
    role_label = _format_issue_role(issue.role)
    entity_label = issue.entity_id or "unknown entity"

    if issue.issue == "missing_entity":
        return f"{severity}: {role_label} sensor {entity_label} could not be found."

    if issue.issue == "entity_disabled":
        disabled_by = str(issue.observed or "").strip().replace("_", " ")
        reason = f" (disabled by {disabled_by})" if disabled_by else ""
        return (
            f"{severity}: {role_label} sensor {entity_label} is disabled{reason}. "
            "Re-enable it in Home Assistant."
        )

    if issue.issue == "missing_device_class":
        expected = issue.expected or "the expected device class"
        return (
            f"{severity}: {role_label} sensor {entity_label} is missing a device class. "
            f"Set it to '{expected}'."
        )

    if issue.issue == "unexpected_device_class":
        expected = issue.expected or "the expected class"
        observed = issue.observed or "unknown"
        return (
            f"{severity}: {role_label} sensor {entity_label} reports device class "
            f"'{observed}' but expected '{expected}'."
        )

    if issue.issue == "unexpected_state_class":
        expected = issue.expected or "the expected state class"
        observed = issue.observed or "unknown"
        return (
            f"{severity}: {role_label} sensor {entity_label} reports state class "
            f"'{observed}' but expected {expected}."
        )

    if issue.issue == "missing_state_class":
        expected = issue.expected or "a supported state class"
        return (
            f"{severity}: {role_label} sensor {entity_label} is missing a state class. "
            f"Set it to {expected}."
        )

    if issue.issue == "unexpected_unit":
        expected_units = issue.expected or "supported units"
        observed_unit = issue.observed or "unknown"
        return (
            f"{severity}: {role_label} sensor {entity_label} uses unit '{observed_unit}' "
            f"but expected {expected_units}."
        )

    if issue.issue == "missing_unit":
        expected_units = issue.expected or "a supported unit"
        return (
            f"{severity}: {role_label} sensor {entity_label} is missing a unit of measurement. "
            f"Provide {expected_units}."
        )

    if issue.issue == "invalid_sensor_domain":
        return (
            f"{severity}: {role_label} entity {entity_label} isn't a sensor. "
            "Select a sensor entity for this role."
        )

    if issue.issue == "unavailable_state":
        observed_state = (issue.observed or "").strip().lower()
        if observed_state == "unknown":
            return f"{severity}: {role_label} sensor {entity_label} hasn't reported a value yet."
        return f"{severity}: {role_label} sensor {entity_label} is currently unavailable."

    if issue.issue == "empty_state":
        return f"{severity}: {role_label} sensor {entity_label} hasn't reported a value yet."

    if issue.issue == "stale_state":
        threshold = issue.expected or "a short time"
        age = issue.observed or "a while"
        return (
            f"{severity}: {role_label} sensor {entity_label} hasn't updated in over {threshold}. "
            f"Last update was {age} ago."
        )

    if issue.issue == "non_numeric_state":
        observed_value = issue.observed or "unknown"
        return (
            f"{severity}: {role_label} sensor {entity_label} reported a non-numeric reading "
            f"'{observed_value}'. Provide a numeric value."
        )

    if issue.issue == "shared_entity":
        observed_roles = []
        if issue.observed:
            observed_roles = [part.strip() for part in str(issue.observed).split(",") if part.strip()]
        other_roles_label, count = _format_role_list(observed_roles)
        role_word = "roles" if count > 1 else "role"
        return (
            f"{severity}: {role_label} sensor {entity_label} is already linked to the "
            f"{other_roles_label} {role_word}. Choose a dedicated sensor for each role."
        )

    message = f"{severity}: {role_label} sensor {entity_label} reported issue '{issue.issue}'"
    if issue.expected or issue.observed:
        message += f" (expected {issue.expected or 'n/a'}, observed {issue.observed or 'n/a'})"
    return message


def collate_issue_messages(issues: Iterable[SensorValidationIssue]) -> str:
    """Return a human friendly summary for diagnostics and notifications."""

    return "\n".join(_format_sensor_issue(issue) for issue in issues)


__all__ = ["SensorValidationIssue", "SensorValidationResult", "validate_sensor_links", "collate_issue_messages", "recommended_stale_after"]


def _has_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return True


def _augment_with_registry_attributes(
    attributes: Mapping[str, Any], registry_entry: Any
) -> dict[str, Any]:
    """Merge relevant metadata from ``registry_entry`` into ``attributes``."""

    merged: dict[str, Any] = dict(attributes)

    def _setdefault(key: str, value: Any) -> None:
        if not _has_value(merged.get(key)) and _has_value(value):
            merged[key] = value

    _setdefault("device_class", getattr(registry_entry, "device_class", None))
    _setdefault(
        "original_device_class",
        getattr(registry_entry, "original_device_class", None),
    )
    _setdefault(
        "unit_of_measurement", getattr(registry_entry, "unit_of_measurement", None)
    )

    capabilities = getattr(registry_entry, "capabilities", None)
    if isinstance(capabilities, Mapping):
        for key in (
            "state_class",
            "unit_of_measurement",
            "suggested_display_unit",
            "suggested_unit_of_measurement",
        ):
            if key in capabilities:
                _setdefault(key, capabilities.get(key))

    return merged


def _get_entity_registry(hass: HomeAssistant) -> Any:
    """Return the entity registry when available."""

    if er is None:  # pragma: no cover - handled in tests via monkeypatching
        return None

    get_registry = getattr(er, "async_get", None)
    if get_registry is None:  # pragma: no cover - defensive
        return None

    try:
        return get_registry(hass)
    except Exception:  # pragma: no cover - best effort access
        return None

