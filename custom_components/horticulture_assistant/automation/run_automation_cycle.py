import logging
from pathlib import Path
from datetime import datetime

from .helpers import iter_profiles, append_json_log

# Global override: disable automation if False
ENABLE_AUTOMATION = False

_LOGGER = logging.getLogger(__name__)

def run_automation_cycle(base_path: str = "plants") -> None:
    """
    Run one cycle of automated irrigation checks for all plant profiles.
    Scans the plants directory for profile JSON files, checks soil moisture against thresholds,
    and triggers irrigation actuators if needed.
    """
    # Global override check
    if not ENABLE_AUTOMATION:
        _LOGGER.info("Automation is globally disabled (ENABLE_AUTOMATION=False). Skipping automation cycle.")
        return

    plants_dir = Path(base_path)
    if not plants_dir.is_dir():
        _LOGGER.error("Plants directory not found: %s", plants_dir)
        return

    profiles = list(iter_profiles(base_path))
    if not profiles:
        _LOGGER.info("No plant profile JSON files found in %s. Nothing to do.", plants_dir)
        return

    for plant_id, profile_data in profiles:

        # Check if irrigation is enabled for this plant
        irrigation_enabled = True
        if isinstance(profile_data.get("actuators"), dict):
            irrigation_enabled = profile_data["actuators"].get("irrigation_enabled", True)
        if not irrigation_enabled or profile_data.get("irrigation_enabled") is False or \
           (isinstance(profile_data.get("general"), dict) and profile_data["general"].get("irrigation_enabled") is False):
            _LOGGER.info("Irrigation is disabled in the profile for plant %s. Skipping irrigation check.", plant_id)
            continue

        # Get latest sensor data (especially soil moisture) for this plant
        sensor_data = {}
        if isinstance(profile_data.get("general"), dict):
            sensor_data = profile_data["general"].get("latest_env", {}) or {}
        if not sensor_data:
            # Also allow top-level latest_env if profile might store it there
            sensor_data = profile_data.get("latest_env", {})
        if not sensor_data:
            _LOGGER.warning("No latest sensor data found for plant %s. Skipping.", plant_id)
            continue

        # Determine soil moisture threshold
        thresholds = profile_data.get("thresholds", {})
        threshold_value = None
        if "soil_moisture_min" in thresholds:
            threshold_value = thresholds["soil_moisture_min"]
        elif "soil_moisture_pct" in thresholds:
            threshold_value = thresholds["soil_moisture_pct"]
        elif "soil_moisture" in thresholds:
            threshold_value = thresholds["soil_moisture"]
        else:
            _LOGGER.error("No soil moisture threshold defined for plant %s. Skipping.", plant_id)
            continue

        # Get current soil moisture reading from sensor_data
        current_moisture = None
        for key in ("soil_moisture", "soil_moisture_pct", "moisture", "vwc"):
            if key in sensor_data:
                current_moisture = sensor_data[key]
                break
        if current_moisture is None:
            _LOGGER.error("No current soil moisture reading available for plant %s. Skipping.", plant_id)
            continue

        # Convert values to float for comparison
        try:
            current_val = float(current_moisture)
        except (TypeError, ValueError):
            _LOGGER.error("Invalid soil moisture value for plant %s: %s", plant_id, current_moisture)
            continue
        try:
            if isinstance(threshold_value, (list, tuple)):
                threshold_val = float(threshold_value[0])
            else:
                threshold_val = float(threshold_value)
        except (TypeError, ValueError):
            _LOGGER.error("Invalid threshold value for plant %s: %s", plant_id, threshold_value)
            continue

        # Compare moisture against threshold and take action
        triggered = False
        if current_val < threshold_val:
            _LOGGER.info("Soil moisture below threshold for plant %s (%.2f < %.2f). Triggering irrigation.", plant_id, current_val, threshold_val)
            try:
                # Trigger the irrigation actuator for this plant
                import custom_components.horticulture_assistant.automation.irrigation_actuator as irrigation_actuator
                irrigation_actuator.trigger_irrigation_actuator(plant_id=plant_id, trigger=True, base_path=base_path)
            except Exception as e:
                _LOGGER.error("Failed to trigger irrigation actuator for plant %s: %s", plant_id, e)
            else:
                triggered = True
        else:
            _LOGGER.info("Soil moisture sufficient for plant %s (%.2f >= %.2f). No irrigation needed.", plant_id, current_val, threshold_val)
            triggered = False

        # Log the outcome to irrigation_log.json for the plant (append entry with timestamp)
        entry = {
            "timestamp": datetime.now().isoformat(),
            "soil_moisture": current_val,
            "threshold": threshold_val,
            "triggered": triggered,
        }
        log_file = plants_dir / str(plant_id) / "irrigation_log.json"
        try:
            append_json_log(log_file, entry)
        except Exception as e:
            _LOGGER.error("Failed to write irrigation log for plant %s: %s", plant_id, e)
