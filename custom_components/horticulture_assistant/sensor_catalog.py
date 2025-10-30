"""Helpers for suggesting relevant sensors during configuration."""

from __future__ import annotations

import inspect
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import Enum
from typing import Any

try:  # pragma: no cover - fallback for tests without Home Assistant imports
    from homeassistant.core import HomeAssistant, State
except (ModuleNotFoundError, ImportError):  # pragma: no cover - executed only in test stubs
    from typing import Any as HomeAssistant  # type: ignore
    from typing import Any as State  # type: ignore

from .sensor_validation import EXPECTED_DEVICE_CLASSES, EXPECTED_UNITS


@dataclass(slots=True)
class SensorSuggestion:
    """Represents an entity that likely fulfils a specific measurement role."""

    entity_id: str
    name: str
    score: int
    reason: str


_ROLE_FRIENDLY_NAMES: dict[str, str] = {
    "moisture": "Moisture",
    "temperature": "Temperature",
    "humidity": "Humidity",
    "illuminance": "Light",
    "co2": "CO₂",
    "ec": "Conductivity",
}


def _normalise(value: Any | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, Enum):
        value = value.value
    text = str(value).strip()
    if not text:
        return None
    return text.lower()


def _score_state(role: str, state: State) -> SensorSuggestion | None:
    entity_id = getattr(state, "entity_id", None)
    if not entity_id:
        return None

    attributes = getattr(state, "attributes", {}) or {}
    name = getattr(state, "name", None) or attributes.get("friendly_name") or entity_id
    normalised_name = _normalise(name) or ""
    device_class = _normalise(attributes.get("device_class"))
    expected_device_class = _normalise(
        getattr(EXPECTED_DEVICE_CLASSES.get(role), "value", EXPECTED_DEVICE_CLASSES.get(role))
    )
    unit = _normalise(attributes.get("unit_of_measurement"))
    expected_units = {
        normalised for normalised in (_normalise(unit) for unit in EXPECTED_UNITS.get(role, set())) if normalised
    }

    score = 0
    reasons: list[str] = []

    if expected_device_class:
        if device_class == expected_device_class:
            score += 5
            reasons.append("device class matches")
        elif device_class:
            score += 2
            reasons.append("device class similar")
    if expected_units:
        if unit in expected_units:
            score += 4
            reasons.append("unit matches")
        elif unit:
            score += 1
            reasons.append("unit present")
    if role in entity_id:
        score += 2
        reasons.append("role in entity id")
    if role in normalised_name:
        score += 2
        reasons.append("role in name")

    if not score:
        return None

    reason = ", ".join(reasons) if reasons else "matched"
    friendly_name = name if isinstance(name, str) else entity_id
    return SensorSuggestion(entity_id=entity_id, name=friendly_name, score=score, reason=reason)


def collect_sensor_suggestions(
    hass: HomeAssistant, roles: Iterable[str], limit: int = 5
) -> dict[str, list[SensorSuggestion]]:
    """Return a mapping of measurement role to candidate entity suggestions."""

    suggestions: dict[str, list[SensorSuggestion]] = {role: [] for role in set(roles)}
    if not getattr(hass, "states", None):  # pragma: no cover - defensive guard
        return suggestions

    states = hass.states
    entity_ids_iter: Iterable[Any] | None = None

    entity_ids_attr = getattr(states, "entity_ids", None)
    if callable(entity_ids_attr):
        entity_ids_iter = entity_ids_attr()
    elif isinstance(entity_ids_attr, Iterable):
        entity_ids_iter = entity_ids_attr

    if entity_ids_iter is None:
        entity_ids_getter = getattr(states, "async_entity_ids", None)
        if callable(entity_ids_getter):
            maybe_iter = entity_ids_getter()
            if inspect.isawaitable(maybe_iter):
                close = getattr(maybe_iter, "close", None)
                if callable(close):
                    close()
                mapping = getattr(states, "_states", None)
                entity_ids_iter = mapping.keys() if isinstance(mapping, Mapping) else ()
            else:
                entity_ids_iter = maybe_iter

    if entity_ids_iter is None and isinstance(states, Mapping):
        entity_ids_iter = states.keys()

    entity_ids = [str(entity_id) for entity_id in (entity_ids_iter or ())]
    for entity_id in entity_ids:
        state = hass.states.get(entity_id)
        if state is None:
            continue
        domain = getattr(state, "domain", None) or entity_id.split(".")[0]
        if domain != "sensor":
            continue
        for role in suggestions:
            suggestion = _score_state(role, state)
            if suggestion is None:
                continue
            suggestions[role].append(suggestion)

    for role, items in suggestions.items():
        if not items:
            continue
        items.sort(key=lambda item: (-item.score, item.name.lower(), item.entity_id))
        suggestions[role] = items[:limit]

    return suggestions


def format_sensor_hints(suggestions: dict[str, list[SensorSuggestion]]) -> str:
    """Format a human-readable hint listing suggestions per role."""

    lines: list[str] = []
    for role in sorted(suggestions.keys()):
        friendly = _ROLE_FRIENDLY_NAMES.get(role, role.title())
        items = suggestions[role]
        if not items:
            lines.append(f"{friendly}: No matching sensors detected.")
            continue
        formatted = ", ".join(f"{item.name} ({item.entity_id})" for item in items)
        lines.append(f"{friendly}: {formatted}")
    return "\n".join(lines)


__all__ = ["SensorSuggestion", "collect_sensor_suggestions", "format_sensor_hints"]
