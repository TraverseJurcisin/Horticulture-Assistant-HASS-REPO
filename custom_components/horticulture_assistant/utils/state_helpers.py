"""Utility helpers for working with Home Assistant state values."""

from __future__ import annotations

import logging
import re
from collections.abc import Iterable
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

__all__ = ["get_numeric_state", "normalize_entities", "aggregate_sensor_values"]

# Pre-compiled pattern used to extract a numeric portion from a string. This
# avoids recompiling the regex for every state lookup and handles optional
# sign and decimal point.
_NUM_RE = re.compile(r"[-+]?[0-9]*\.?[0-9]+")


def get_numeric_state(hass: HomeAssistant, entity_id: str) -> float | None:
    """Return the numeric state of ``entity_id`` or ``None`` if unavailable.

    The helper accepts values with optional units appended, such as
    ``"25 °C"`` or ``"5.5pH"``. Non-numeric states return ``None`` and a
    debug message is logged. Values like ``"unknown"`` or ``"unavailable````
    are also treated as missing.
    """

    state = hass.states.get(entity_id)
    if not state or state.state in {"unknown", "unavailable"}:
        _LOGGER.debug("State unavailable: %s", entity_id)
        return None

    value = str(state.state).replace(",", "").strip()
    try:
        return float(value)
    except (ValueError, TypeError):
        match = _NUM_RE.search(value)
        if match:
            try:
                return float(match.group(0))
            except (ValueError, TypeError):
                pass
        _LOGGER.warning("State of %s is not numeric: %s", entity_id, value)
        return None


def normalize_entities(val: str | Iterable[str] | None, default: str) -> list[str]:
    """Return a list of entity IDs from ``val`` or ``default``.

    String inputs may be comma or semicolon separated. Any whitespace is
    stripped and duplicate entries removed while preserving order.
    """

    if not val:
        return [default]

    entities: Iterable[str]
    if isinstance(val, str):
        entities = [p.strip() for p in re.split(r"[;,]", val) if p.strip()]
    else:
        entities = [str(v).strip() for v in val if str(v).strip()]

    seen: set[str] = set()
    result: list[str] = []
    for ent in entities:
        if ent not in seen:
            seen.add(ent)
            result.append(ent)
    return result if result else [default]


def aggregate_sensor_values(
    hass: HomeAssistant, entity_ids: str | Iterable[str]
) -> float | None:
    """Return the average or median value of multiple sensors."""

    ids = [entity_ids] if isinstance(entity_ids, str) else list(entity_ids)
    values = [get_numeric_state(hass, eid) for eid in ids]
    values = [v for v in values if v is not None]
    if not values:
        return None
    if len(values) > 2:
        from statistics import median

        return median(values)
    return sum(values) / len(values)
