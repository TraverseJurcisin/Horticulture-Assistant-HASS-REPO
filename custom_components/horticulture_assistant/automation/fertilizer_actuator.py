# File: custom_components/horticulture_assistant/automation/fertilizer_actuator.py

import json
import logging
from pathlib import Path

try:
    from homeassistant.core import HomeAssistant
except ImportError:
    HomeAssistant = None  # type: ignore

_LOGGER = logging.getLogger(__name__)

def trigger_fertilizer_actuator(plant_id: str, trigger: bool, base_path: str, hass: HomeAssistant = None) -> None:
    """Toggle the fertilizer switch for a given plant's actuator on or off.

    Loads the plant's profile from a JSON file at base_path/plant_id.json to retrieve the fertilizer actuator entity ID.
    If a Home Assistant instance is provided and the profile defines a fertilizer switch, this function calls the 
    appropriate Home Assistant service (switch.turn_on or switch.turn_off) to activate or deactivate the switch.
    Logs the action taken. If no fertilizer actuator is defined or if no Home Assistant instance is provided, no action is taken.
    """
    # Construct the path to the plant profile JSON file
    profile_file = Path(base_path) / f"{plant_id}.json"
    if not profile_file.is_file():
        _LOGGER.error("Plant profile file not found: %s", profile_file)
        return

    # Load the plant profile data from JSON
    try:
        with open(profile_file, "r", encoding="utf-8") as f:
            profile_data = json.load(f)
    except Exception as e:
        _LOGGER.error("Error reading plant profile file %s: %s", profile_file, e)
        return

    # Retrieve the fertilizer actuator entity from the profile (if present)
    actuators = profile_data.get("actuator_entities") or profile_data.get("actuators") or {}
    fertilizer_entity = None
    if isinstance(actuators, dict):
        fertilizer_entity = (actuators.get("fertilizer_switch") or
                              actuators.get("fertilizer_entity_id") or
                              actuators.get("fertilizer_entity") or
                              actuators.get("fertilizer"))
    if not fertilizer_entity:
        # No fertilizer actuator defined in profile; skip triggering
        _LOGGER.info("No fertilizer actuator defined for plant '%s'; skipping fertilizer action.", plant_id)
        return

    if hass is None:
        # Home Assistant instance is not provided; cannot perform the service call
        _LOGGER.info("Home Assistant instance not provided; cannot trigger fertilizer for plant '%s'.", plant_id)
        return

    # Determine the service call based on trigger value
    service_domain = "switch"
    service_action = "turn_on" if trigger else "turn_off"
    service_data = {"entity_id": fertilizer_entity}

    try:
        # Call the Home Assistant service to toggle the switch
        hass.services.call(service_domain, service_action, service_data)
        _LOGGER.info("Fertilizer actuator for plant '%s' turned %s (entity: %s).",
                     plant_id, "on" if trigger else "off", fertilizer_entity)
    except Exception as e:
        _LOGGER.error("Failed to call service to turn %s fertilizer for plant '%s': %s",
                      "on" if trigger else "off", plant_id, e)