"""Profile device health evaluation helpers."""

from __future__ import annotations

import math
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from .utils.entry_helpers import ProfileContext

try:  # pragma: no cover - Home Assistant runtime provides real classes
    from homeassistant.core import HomeAssistant, State
except (ModuleNotFoundError, ImportError):  # pragma: no cover - tests provide stubs

    class State:  # type: ignore[too-few-public-methods]
        """Fallback Home Assistant state used in unit tests."""

        def __init__(self, state: str | None = None, *, attributes: Mapping[str, Any] | None = None):
            self.state = state if state is not None else "unknown"
            self.attributes = dict(attributes or {})
            self.last_changed = None
            self.last_updated = None

    class HomeAssistant:  # type: ignore[too-few-public-methods]
        """Fallback Home Assistant object used when HA is unavailable."""

        def __init__(self) -> None:
            self.states = {}


_NUMERIC_PATTERN = re.compile(r"[-+]?(?:\d+(?:[.,]\d+)?|\.\d+)(?:[eE][-+]?\d+)?")


@dataclass(slots=True)
class ProfileMonitorIssue:
    """Represents a deviation discovered while evaluating a profile device."""

    severity: str
    summary: str
    role: str | None = None
    entity_id: str | None = None
    detail: str | None = None

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON serialisable representation of the issue."""

        payload: dict[str, Any] = {"severity": self.severity, "summary": self.summary}
        if self.role:
            payload["role"] = self.role
        if self.entity_id:
            payload["entity_id"] = self.entity_id
        if self.detail:
            payload["detail"] = self.detail
        return payload


@dataclass(slots=True)
class ProfileMonitorSensorSnapshot:
    """State snapshot captured while evaluating a profile sensor."""

    role: str
    entity_id: str
    state: str | None
    value: float | None
    available: bool
    status: str
    last_changed: datetime | None
    last_updated: datetime | None
    unit_of_measurement: str | None

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON serialisable snapshot payload."""

        payload: dict[str, Any] = {
            "role": self.role,
            "entity_id": self.entity_id,
            "state": self.state,
            "available": self.available,
            "status": self.status,
        }
        if self.value is not None:
            payload["value"] = self.value
        if self.unit_of_measurement:
            payload["unit_of_measurement"] = self.unit_of_measurement
        if self.last_changed:
            payload["last_changed"] = self.last_changed.isoformat()
        if self.last_updated:
            payload["last_updated"] = self.last_updated.isoformat()
        return payload


@dataclass(slots=True)
class ProfileMonitorResult:
    """Outcome of evaluating a profile device."""

    context: ProfileContext
    issues: tuple[ProfileMonitorIssue, ...]
    sensors: tuple[ProfileMonitorSensorSnapshot, ...]
    last_sample_at: datetime | None

    @property
    def health(self) -> str:
        """Return the overall health label for the profile."""

        if any(issue.severity == "problem" for issue in self.issues):
            return "problem"
        if self.issues:
            return "attention"
        return "ok"

    def issues_for(self, *severities: str) -> tuple[ProfileMonitorIssue, ...]:
        """Return the subset of issues matching ``severities``."""

        if not severities:
            return self.issues
        return tuple(issue for issue in self.issues if issue.severity in severities)

    def as_attributes(self, *, severities: Sequence[str] | None = None) -> dict[str, Any]:
        """Return state attributes for use on Home Assistant entities."""

        issues = (issue.as_dict() for issue in self.issues if not severities or issue.severity in severities)
        attrs: dict[str, Any] = {
            "issues": list(issues),
            "sensor_count": len(self.sensors),
            "health": self.health,
        }
        if self.last_sample_at:
            attrs["last_sample_at"] = self.last_sample_at.isoformat()
        attrs["sensors"] = [snapshot.as_dict() for snapshot in self.sensors]
        return attrs

    def as_diagnostics(self) -> dict[str, Any]:
        """Return a diagnostics payload summarising the evaluation."""

        payload = self.as_attributes()
        payload["profile_id"] = self.context.id
        payload["profile_name"] = self.context.name
        return payload


class ProfileMonitor:
    """Evaluate the health of a profile's linked sensors."""

    def __init__(self, hass: HomeAssistant, context: ProfileContext) -> None:
        self._hass = hass
        self._context = context

    def evaluate(self) -> ProfileMonitorResult:
        """Evaluate linked sensors and return a monitor result."""

        states = getattr(self._hass, "states", None)
        issues: list[ProfileMonitorIssue] = []
        snapshots: list[ProfileMonitorSensorSnapshot] = []
        latest: datetime | None = None

        for role, entity_ids in self._context.sensors.items():
            bounds = _threshold_bounds_for_role(self._context, role)
            for entity_id in entity_ids:
                snapshot, new_issues, timestamp = _evaluate_sensor(states, role, entity_id, bounds)
                snapshots.append(snapshot)
                issues.extend(new_issues)
                if timestamp and (latest is None or timestamp > latest):
                    latest = timestamp

        return ProfileMonitorResult(
            self._context,
            tuple(issues),
            tuple(snapshots),
            latest,
        )


def _evaluate_sensor(
    states: Any,
    role: str,
    entity_id: str,
    bounds: tuple[float | None, float | None],
) -> tuple[ProfileMonitorSensorSnapshot, list[ProfileMonitorIssue], datetime | None]:
    """Evaluate ``entity_id`` for ``role`` against ``bounds``."""

    issues: list[ProfileMonitorIssue] = []
    state_obj: State | None = None
    if states is not None and hasattr(states, "get"):
        state_obj = states.get(entity_id)

    last_timestamp: datetime | None = None
    last_changed: datetime | None = None
    last_updated: datetime | None = None
    unit = None
    state_value: str | None = None
    numeric_value: float | None = None
    available = False
    status = "missing"

    if state_obj is None:
        issues.append(
            ProfileMonitorIssue(
                "attention",
                "sensor_missing",
                role=role,
                entity_id=entity_id,
                detail="Linked sensor could not be found.",
            )
        )
    else:
        state_value = getattr(state_obj, "state", None)
        attributes = getattr(state_obj, "attributes", {}) or {}
        unit = attributes.get("unit_of_measurement")
        last_changed = _coerce_datetime(getattr(state_obj, "last_changed", None))
        last_updated = _coerce_datetime(getattr(state_obj, "last_updated", None))
        last_timestamp = _latest_timestamp(last_changed, last_updated)
        if state_value in (None, "unknown", "unavailable"):
            status = "unavailable"
            issues.append(
                ProfileMonitorIssue(
                    "attention",
                    "sensor_unavailable",
                    role=role,
                    entity_id=entity_id,
                    detail="Sensor is reporting as unknown or unavailable.",
                )
            )
        else:
            value = _coerce_float(state_value)
            if value is None:
                status = "non_numeric"
                issues.append(
                    ProfileMonitorIssue(
                        "attention",
                        "sensor_non_numeric",
                        role=role,
                        entity_id=entity_id,
                        detail=f"Received non-numeric state '{state_value}'.",
                    )
                )
            else:
                available = True
                numeric_value = value
                status = "ok"
                low, high = bounds
                if low is not None and value < low:
                    status = "below_min"
                    issues.append(
                        ProfileMonitorIssue(
                            "problem",
                            "sensor_below_minimum",
                            role=role,
                            entity_id=entity_id,
                            detail=f"{value} is below the minimum target of {low}.",
                        )
                    )
                elif high is not None and value > high:
                    status = "above_max"
                    issues.append(
                        ProfileMonitorIssue(
                            "problem",
                            "sensor_above_maximum",
                            role=role,
                            entity_id=entity_id,
                            detail=f"{value} exceeds the maximum target of {high}.",
                        )
                    )

    snapshot = ProfileMonitorSensorSnapshot(
        role=role,
        entity_id=entity_id,
        state=state_value,
        value=numeric_value,
        available=available,
        status=status,
        last_changed=last_changed,
        last_updated=last_updated,
        unit_of_measurement=unit,
    )
    return snapshot, issues, last_timestamp


def _coerce_float(value: Any) -> float | None:
    """Return ``value`` coerced to ``float`` when possible."""

    def _valid(number: float) -> float | None:
        if math.isnan(number) or math.isinf(number):
            return None
        return number

    if isinstance(value, int | float):
        return _valid(float(value))
    if isinstance(value, str):
        normalised = _normalise_numeric_text(value)
        if normalised is not None:
            try:
                return _valid(float(normalised))
            except ValueError:
                pass
        match = _NUMERIC_PATTERN.search(value)
        if match is None:
            return None
        candidate = _normalise_numeric_text(match.group(0))
        if candidate is None:
            return None
        try:
            return _valid(float(candidate))
        except ValueError:
            return None
    return None


def _normalise_numeric_text(value: str) -> str | None:
    """Return ``value`` normalised for ``float`` parsing."""

    text = value.strip()
    if not text:
        return None

    sign = ""
    if text[0] in "+-":
        sign, text = text[0], text[1:]

    text = text.strip().replace("\u00a0", "").replace(" ", "").replace("_", "")
    if not text:
        return None

    exponent = ""
    exp_match = re.search(r"[eE][-+]?\d+$", text)
    if exp_match:
        exponent = exp_match.group(0)
        text = text[: exp_match.start()]
        if not text:
            return None

    if "," in text and "." in text:
        last_comma = text.rfind(",")
        last_dot = text.rfind(".")
        if last_comma > last_dot:
            text = text.replace(".", "")
            text = text.replace(",", ".", 1)
            text = text.replace(",", "")
        else:
            text = text.replace(",", "")
    elif "," in text:
        if text.count(",") == 1:
            integer, fractional = text.split(",", 1)
            if integer.isdigit() and fractional.isdigit() and len(fractional) == 3:
                text = integer + fractional
            else:
                if integer and fractional:
                    text = f"{integer}.{fractional}"
                elif fractional:
                    text = f"0.{fractional}"
                else:
                    text = integer
        else:
            text = text.replace(",", "")
    elif text.count(".") > 1:
        if text.replace(".", "").isdigit():
            text = text.replace(".", "")
        else:
            head, _, remainder = text.partition(".")
            text = f"{head}.{remainder.replace('.', '')}"

    text = text.strip()
    if not text:
        return None

    normalised = f"{sign}{text}{exponent}" if sign or exponent else text
    return normalised


def _coerce_datetime(value: Any) -> datetime | None:
    """Return ``value`` when it is a ``datetime`` instance."""

    return value if isinstance(value, datetime) else None


def _latest_timestamp(*timestamps: datetime | None) -> datetime | None:
    """Return the freshest timestamp from ``timestamps`` when available."""

    candidates = [candidate for candidate in timestamps if isinstance(candidate, datetime)]
    if not candidates:
        return None
    return max(candidates)


ROLE_ALIASES: Mapping[str, tuple[str, ...]] = {
    "moisture": ("soil_moisture", "substrate_moisture"),
    "soil_moisture": ("moisture",),
    "humidity": ("relative_humidity",),
    "temperature": ("air_temperature", "temp"),
    "illuminance": ("light", "lux"),
    "light": ("illuminance", "lux"),
    "conductivity": ("ec", "electrical_conductivity"),
    "ec": ("conductivity",),
    "co2": ("carbon_dioxide",),
}


def _threshold_bounds_for_role(context: ProfileContext, role: str) -> tuple[float | None, float | None]:
    """Return ``(min, max)`` bounds for ``role`` if configured."""

    low: float | None = None
    high: float | None = None
    for candidate in _candidate_threshold_keys(role):
        minimum = context.get_threshold(f"{candidate}_min")
        maximum = context.get_threshold(f"{candidate}_max")
        if low is None and minimum is not None:
            low = _coerce_float(minimum)
        if high is None and maximum is not None:
            high = _coerce_float(maximum)
        if low is not None and high is not None:
            break
    return low, high


def _candidate_threshold_keys(role: str) -> Iterable[str]:
    """Yield threshold key prefixes for ``role``."""

    seen: set[str] = set()
    normalised = str(role or "").strip().lower()
    if not normalised:
        return ()
    to_visit = [normalised]
    to_visit.extend(alias for alias in ROLE_ALIASES.get(normalised, ()) if alias not in to_visit)
    for candidate in to_visit:
        if candidate and candidate not in seen:
            seen.add(candidate)
            yield candidate
