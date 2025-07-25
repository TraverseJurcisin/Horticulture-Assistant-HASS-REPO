# File: custom_components/horticulture_assistant/automation/fertilizer_actuator.py

from __future__ import annotations

import logging

try:
    from homeassistant.core import HomeAssistant
except ImportError:  # pragma: no cover - Home Assistant not available during tests
    HomeAssistant = None  # type: ignore

from .actuator_utils import trigger_actuator

_LOGGER = logging.getLogger(__name__)


def trigger_fertilizer_actuator(
    plant_id: str,
    trigger: bool,
    base_path: str,
    hass: HomeAssistant | None = None,
) -> None:
    """Toggle the fertilizer switch defined in a plant profile."""

    trigger_actuator(
        plant_id=plant_id,
        actuator="fertilizer",
        trigger=trigger,
        base_path=base_path,
        hass=hass,
    )
