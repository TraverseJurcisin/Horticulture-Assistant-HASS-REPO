# File: custom_components/horticulture_assistant/utils/daily_report_builder.py

import logging
import json
import os
from datetime import datetime
from homeassistant.core import HomeAssistant

from custom_components.horticulture_assistant.utils.plant_profile_loader import load_profile

_LOGGER = logging.getLogger(__name__)

def get_state_value(hass: HomeAssistant, entity_id: str) -> float | None:
    """Retrieve the state of a Home Assistant entity as a float, or None if unavailable/invalid."""
    state = hass.states.get(entity_id)
    if not state or state.state in ("unknown", "unavailable"):
        _LOGGER.debug("Sensor %s is unavailable or unknown; skipping.", entity_id)
        return None
    try:
        return float(state.state)
    except (ValueError, TypeError):
        _LOGGER.warning("State of %s is not a numeric value: %s", entity_id, state.state)
        return None

def build_daily_report(hass: HomeAssistant, plant_id: str) -> dict:
    """Collect current sensor data and profile info for a plant and compile a daily report."""
    # Load plant profile (JSON or YAML) by plant_id
    profile = load_profile(plant_id=plant_id, base_dir=hass.config.path("plants"))
    if not profile:
        _LOGGER.error("Plant profile for '%s' not found or empty.", plant_id)
        return {}

    # Determine current lifecycle stage from profile (if available)
    stage = (profile.get("general", {}).get("lifecycle_stage")
             or profile.get("general", {}).get("stage")
             or "unknown")

    # Static thresholds and nutrient targets from profile
    thresholds = profile.get("thresholds", {})  # environmental or nutrient thresholds
    nutrient_targets = profile.get("nutrients", {})  # target nutrient levels
    # Tags may be defined at root or under 'general'
    tags = profile.get("general", {}).get("tags") or profile.get("tags") or []
    if tags is None:
        tags = []

    # Collect current sensor readings (moisture, EC, temperature, humidity, light)
    sensor_map = profile.get("sensor_entities") or {}
    moisture = get_state_value(hass, sensor_map.get("moisture") or f"sensor.{plant_id}_raw_moisture")
    ec = get_state_value(hass, sensor_map.get("ec") or f"sensor.{plant_id}_raw_ec")
    temperature = get_state_value(hass, sensor_map.get("temperature") or f"sensor.{plant_id}_raw_temperature")
    humidity = get_state_value(hass, sensor_map.get("humidity") or f"sensor.{plant_id}_raw_humidity")
    light = get_state_value(hass, sensor_map.get("light") or f"sensor.{plant_id}_raw_light")

    # Last known yield (e.g., total yield or current yield progress)
    yield_val = profile.get("last_yield")
    if yield_val is None:
        # Attempt to retrieve from a yield sensor if available (e.g., integration's Yield Progress sensor)
        short_id = plant_id[:6]
        possible_yield_entities = [
            f"sensor.{plant_id}_yield",
            f"sensor.plant_{short_id}_yield_progress"
        ]
        for ent in possible_yield_entities:
            y_state = get_state_value(hass, ent)
            if y_state is not None:
                yield_val = y_state
                break

    # Compile the daily report structure
    report = {
        "plant_id": plant_id,
        "timestamp": datetime.now().isoformat(),
        "lifecycle_stage": stage,
        "moisture": moisture,
        "ec": ec,
        "temperature": temperature,
        "humidity": humidity,
        "light": light,
        "yield": yield_val,
        "thresholds": thresholds,
        "nutrients": nutrient_targets,
        "tags": tags,
        "ai_feedback_required": not profile.get("auto_approve_all", False)
    }

    # Save report to disk (under data/daily_reports/<plant_id>-YYYYMMDD.json)
    report_dir = hass.config.path("data", "daily_reports")
    os.makedirs(report_dir, exist_ok=True)
    date_str = datetime.now().strftime("%Y%m%d")
    file_path = os.path.join(report_dir, f"{plant_id}-{date_str}.json")
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        _LOGGER.info("Daily report saved for plant %s at %s", plant_id, file_path)
    except Exception as e:
        _LOGGER.error("Failed to save daily report for %s: %s", plant_id, e)

    return report