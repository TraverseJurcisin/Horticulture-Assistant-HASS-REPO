"""Utility helpers for working with Home Assistant state values."""

from __future__ import annotations

import logging
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

__all__ = ["get_numeric_state"]

def get_numeric_state(hass: HomeAssistant, entity_id: str) -> float | None:
    """Return the state of ``entity_id`` cast to ``float`` if available."""
    state = hass.states.get(entity_id)
    if not state or state.state in ("unknown", "unavailable"):
        _LOGGER.debug("State unavailable: %s", entity_id)
        return None
    try:
        return float(state.state)
    except (ValueError, TypeError):
        _LOGGER.warning("State of %s is not numeric: %s", entity_id, state.state)
        return None
