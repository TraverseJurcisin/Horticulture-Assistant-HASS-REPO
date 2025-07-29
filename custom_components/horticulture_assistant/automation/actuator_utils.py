from __future__ import annotations

import logging
from pathlib import Path

from ..utils import load_json

try:
    from homeassistant.core import HomeAssistant
except ImportError:  # pragma: no cover - Home Assistant not available during tests
    HomeAssistant = None  # type: ignore

_LOGGER = logging.getLogger(__name__)


def trigger_actuator(
    plant_id: str,
    actuator: str,
    trigger: bool,
    base_path: str,
    hass: HomeAssistant | None = None,
) -> None:
    """Toggle an actuator switch defined in a plant profile."""

    profile_file = Path(base_path) / f"{plant_id}.json"
    if not profile_file.is_file():
        _LOGGER.error("Plant profile file not found: %s", profile_file)
        return

    try:
        profile_data = load_json(str(profile_file))
    except Exception as e:  # pragma: no cover - unlikely to happen in tests
        _LOGGER.error("Error reading plant profile file %s: %s", profile_file, e)
        return

    actuators = profile_data.get("actuator_entities") or profile_data.get("actuators") or {}
    entity: str | None = None
    if isinstance(actuators, dict):
        entity = (
            actuators.get(f"{actuator}_switch")
            or actuators.get(f"{actuator}_entity_id")
            or actuators.get(f"{actuator}_entity")
            or actuators.get(actuator)
        )

    if not entity:
        _LOGGER.info("No %s actuator defined for plant '%s'; skipping action.", actuator, plant_id)
        return

    if hass is None:
        _LOGGER.info(
            "Home Assistant instance not provided; cannot trigger %s for plant '%s'.",
            actuator,
            plant_id,
        )
        return

    service_domain = "switch"
    service_action = "turn_on" if trigger else "turn_off"
    service_data = {"entity_id": entity}

    try:
        hass.services.call(service_domain, service_action, service_data)
        _LOGGER.info(
            "%s actuator for plant '%s' turned %s (entity: %s).",
            actuator.capitalize(),
            plant_id,
            "on" if trigger else "off",
            entity,
        )
    except Exception as e:  # pragma: no cover - service call errors not tested
        _LOGGER.error(
            "Failed to call service to turn %s %s for plant '%s': %s",
            "on" if trigger else "off",
            actuator,
            plant_id,
            e,
        )
