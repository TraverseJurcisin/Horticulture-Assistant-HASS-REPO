"""Helpers for validating sensor entity assignments."""

from __future__ import annotations

import math
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import TYPE_CHECKING, Any

try:  # pragma: no cover - fallback for tests without Home Assistant
    from homeassistant import const as ha_const
except ModuleNotFoundError:  # pragma: no cover - executed in stubbed env
    import types

    ha_const = types.SimpleNamespace(  # type: ignore[assignment]
        CONCENTRATION_PARTS_PER_MILLION="ppm",
        LIGHT_LUX="lx",
        PERCENTAGE="%",
        STATE_UNKNOWN="unknown",
        STATE_UNAVAILABLE="unavailable",
        UnitOfTemperature=types.SimpleNamespace(CELSIUS="°C", FAHRENHEIT="°F"),
    )

try:  # pragma: no cover - fallback for tests
    from homeassistant.components.sensor import SensorDeviceClass
except ModuleNotFoundError:  # pragma: no cover - executed in stubbed env
    from enum import Enum

    class SensorDeviceClass(str, Enum):
        TEMPERATURE = "temperature"
        HUMIDITY = "humidity"
        ILLUMINANCE = "illuminance"
        MOISTURE = "moisture"
        CO2 = "co2"
        CONDUCTIVITY = "conductivity"

if TYPE_CHECKING:  # pragma: no cover - typing only
    from homeassistant.core import HomeAssistant
else:
    HomeAssistant = Any  # type: ignore[assignment]

try:  # pragma: no cover - Home Assistant not available in tests
    from homeassistant.util import dt as dt_util
except (ModuleNotFoundError, ImportError):  # pragma: no cover - executed in stubbed env

    class _FallbackDateTimeModule:  # pragma: no cover - simplified UTC helper for tests
        @staticmethod
        def utcnow() -> datetime:
            return datetime.now(datetime.UTC)

    dt_util = _FallbackDateTimeModule()  # type: ignore[assignment]


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


_LIGHT_LUX = getattr(ha_const, "LIGHT_LUX", "lx")
_PERCENTAGE = getattr(ha_const, "PERCENTAGE", "%")
_UnitOfTemperature = getattr(ha_const, "UnitOfTemperature", None)

_STATE_UNKNOWN = str(getattr(ha_const, "STATE_UNKNOWN", "unknown")).lower()
_STATE_UNAVAILABLE = str(getattr(ha_const, "STATE_UNAVAILABLE", "unavailable")).lower()

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
    "humidity": {_PERCENTAGE, "%", "percent"},
    "moisture": {_PERCENTAGE, "%", "percent"},
    "illuminance": {_LIGHT_LUX, "lx", "lux", "klx", "kilolux"},
    "co2": _CO2_UNITS,
    "ec": {"µS/cm", "uS/cm", "us/cm", "mS/cm", "ds/m", "s/m"},
}

_DEFAULT_STALE_AFTER = timedelta(hours=1)
_ISO_DURATION = re.compile(
    r"^P(?:T(?:(?P<hours>\d+(?:\.\d+)?)H)?(?:(?P<minutes>\d+(?:\.\d+)?)M)?(?:(?P<seconds>\d+(?:\.\d+)?)S)?)$",
    re.IGNORECASE,
)


def recommended_stale_after(update_interval_minutes: float | int | str | timedelta | None) -> timedelta:
    """Return a stale warning threshold suited to ``update_interval_minutes``."""

    minutes = _coerce_minutes(update_interval_minutes)
    if minutes is None or minutes <= 0:
        return _DEFAULT_STALE_AFTER
    dynamic = timedelta(minutes=minutes * 3)
    return dynamic if dynamic > _DEFAULT_STALE_AFTER else _DEFAULT_STALE_AFTER


def _coerce_minutes(value: float | int | str | timedelta | None) -> float | None:
    if value is None:
        return None
    if isinstance(value, timedelta):
        return value.total_seconds() / 60
    if isinstance(value, int | float):
        if math.isnan(value):  # type: ignore[arg-type]
            return None
        return float(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        lower = text.lower()
        for suffix in ("minutes", "minute", "mins", "min", "m"):
            if lower.endswith(suffix) and len(lower) > len(suffix):
                text = lower[: -len(suffix)].strip()
                break
        try:
            return float(text)
        except ValueError:
            pass
        if ":" in text:
            parts = text.split(":")
            try:
                values = [float(part) for part in parts]
            except ValueError:
                values = []
            if values:
                if len(values) == 3:
                    hours, minutes, seconds = values
                elif len(values) == 2:
                    hours, minutes = values
                    seconds = 0.0
                else:
                    hours = 0.0
                    minutes = values[0]
                    seconds = 0.0
                return hours * 60 + minutes + seconds / 60
        match = _ISO_DURATION.match(text)
        if match:
            hours = float(match.group("hours") or 0)
            minutes = float(match.group("minutes") or 0)
            seconds = float(match.group("seconds") or 0)
            return hours * 60 + minutes + seconds / 60
    return None


def _normalise_device_class(value: str | None) -> str | None:
    if value is None:
        return None
    return str(value).lower()


def _normalise_unit(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, Enum):
        value = value.value
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


def _coerce_datetime(*candidates: Any) -> datetime | None:
    for value in candidates:
        if value is None:
            continue
        if isinstance(value, datetime):
            if value.tzinfo is None:
                return value.replace(tzinfo=datetime.UTC)
            return value.astimezone(datetime.UTC)
        text = str(value).strip()
        if not text:
            continue
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            continue
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=datetime.UTC)
        return parsed.astimezone(datetime.UTC)
    return None


def _format_duration(delta: timedelta) -> str:
    seconds = int(delta.total_seconds())
    if seconds <= 0:
        return "less than a minute"
    minutes, seconds = divmod(seconds, 60)
    if minutes < 1:
        return "less than a minute"
    if minutes < 60:
        return _pluralise(minutes, "minute")
    hours, minutes = divmod(minutes, 60)
    if hours < 24:
        if minutes:
            return f"{_pluralise(hours, 'hour')} {_pluralise(minutes, 'minute')}"
        return _pluralise(hours, "hour")
    days, hours = divmod(hours, 24)
    if days < 7:
        if hours:
            return f"{_pluralise(days, 'day')} {_pluralise(hours, 'hour')}"
        return _pluralise(days, "day")
    weeks, days = divmod(days, 7)
    if days:
        return f"{_pluralise(weeks, 'week')} {_pluralise(days, 'day')}"
    return _pluralise(weeks, "week")


def _pluralise(value: int, word: str) -> str:
    suffix = "s" if value != 1 else ""
    return f"{value} {word}{suffix}"


def validate_sensor_links(
    hass: HomeAssistant,
    sensors: Mapping[str, str | Sequence[Any]],
    *,
    stale_after: timedelta | None = None,
) -> SensorValidationResult:
    """Validate a mapping of measurement role to entity ids."""

    errors: list[SensorValidationIssue] = []
    warnings: list[SensorValidationIssue] = []

    stale_after = stale_after if stale_after and stale_after.total_seconds() > 0 else _DEFAULT_STALE_AFTER

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

            attributes = getattr(state, "attributes", {})
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

            raw_state = getattr(state, "state", None)
            state_text = str(raw_state).strip() if raw_state is not None else ""
            if state_text and state_text.lower() not in {_STATE_UNKNOWN, _STATE_UNAVAILABLE}:
                last_updated = _coerce_datetime(
                    getattr(state, "last_updated", None),
                    getattr(state, "last_changed", None),
                )
                if last_updated is not None:
                    now = dt_util.utcnow()
                    age = now - last_updated
                    if age > stale_after:
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


__all__ = [
    "SensorValidationIssue",
    "SensorValidationResult",
    "validate_sensor_links",
    "recommended_stale_after",
    "collate_issue_messages",
]
