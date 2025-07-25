"""Utility helpers for working with Home Assistant state values."""

from __future__ import annotations

import logging
import re
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

from statistics import mean, median

__all__ = ["get_numeric_state", "get_aggregated_state"]

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


def get_aggregated_state(
    hass: HomeAssistant, entity_ids: list[str], *, method: str = "mean"
) -> float | None:
    """Return the aggregated numeric state for ``entity_ids``.

    ``method`` may be ``"mean"`` or ``"median"``. Non-numeric or missing
    states are ignored. ``None`` is returned if no values are available.
    """

    values = [get_numeric_state(hass, eid) for eid in entity_ids]
    vals = [v for v in values if v is not None]
    if not vals:
        return None
    if method == "median" and len(vals) > 1:
        return median(vals)
    return mean(vals)
