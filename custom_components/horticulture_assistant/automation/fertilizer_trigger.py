import json
import logging
from pathlib import Path

_LOGGER = logging.getLogger(__name__)

def fertilizer_trigger(plant_id: str, base_path: str = "plants", sensor_data: dict = None) -> bool:
    """
    Determine whether to trigger fertilization for a given plant based on nutrient levels and thresholds.
    Args:
        plant_id: Identifier of the plant profile.
        base_path: Base directory path where plant profiles are stored (defaults to "plants").
        sensor_data: Dictionary of current sensor readings (keys like 'EC', 'leaf_nitrogen', etc).
    Returns:
        True if fertilization should be triggered, False otherwise.
    """
    if sensor_data is None:
        sensor_data = {}
    # Load plant profile from JSON file
    profile_path = Path(base_path) / f"{plant_id}.json"
    if not profile_path.is_file():
        _LOGGER.error("Plant profile file not found for plant_id: %s", plant_id)
        return False
    try:
        with open(profile_path, "r", encoding="utf-8") as f:
            profile_data = json.load(f)
    except Exception as e:
        _LOGGER.error("Failed to load profile for plant_id %s: %s", plant_id, e)
        return False

    # Check if fertilization is globally enabled for this plant
    fertilizer_enabled = True
    # The profile may include a flag for fertilization in either 'actuators' or top-level keys
    if isinstance(profile_data.get("actuators"), dict):
        fertilizer_enabled = profile_data["actuators"].get("fertilizer_enabled", True)
    # Some profiles might use a top-level or 'general' flag for fertilization
    if not fertilizer_enabled or profile_data.get("fertilizer_enabled") is False or \
       (isinstance(profile_data.get("general"), dict) and profile_data["general"].get("fertilizer_enabled") is False):
        _LOGGER.info("Fertilization is disabled in the profile for plant_id %s. Skipping fertilizer trigger check.", plant_id)
        return False

    # Determine nutrient thresholds to check
    thresholds = profile_data.get("thresholds", {})
    relevant_thresholds = {}
    if isinstance(thresholds, dict):
        for key, value in thresholds.items():
            k_lower = str(key).lower()
            # Skip thresholds that are not related to nutrients (e.g., moisture, temp, light, or known contaminants)
            if "moisture" in k_lower or "temp" in k_lower or "light" in k_lower:
                continue
            if "arsenic" in k_lower or "cadmium" in k_lower or "lead" in k_lower or "mercury" in k_lower:
                continue
            if k_lower == "ph":
                continue
            # If we reach here, consider this threshold relevant for fertilization
            relevant_thresholds[key] = value
    if not relevant_thresholds:
        _LOGGER.error("No nutrient thresholds found in profile for plant_id %s.", plant_id)
        return False

    # Iterate through relevant nutrient thresholds and check current values
    for thresh_key, thresh_value in relevant_thresholds.items():
        # Determine the current reading for this threshold key
        current_reading = None
        # Look in sensor_data for a matching key
        if thresh_key in sensor_data:
            current_reading = sensor_data[thresh_key]
        else:
            # If threshold key ends with unit like '_ppm', try matching without it
            if thresh_key.endswith("_ppm"):
                alt_key = thresh_key[:-4]  # remove the "_ppm"
                if alt_key in sensor_data:
                    current_reading = sensor_data[alt_key]
            # Handle EC as a special case (threshold might be 'ec' or 'ec_min')
            if current_reading is None and (thresh_key.lower() == "ec" or thresh_key.lower() == "ec_min"):
                if "ec" in sensor_data:
                    current_reading = sensor_data["ec"]
                elif "EC" in sensor_data:
                    current_reading = sensor_data["EC"]
        # If not provided in sensor_data, check profile_data for a latest reading
        if current_reading is None:
            latest_env = {}
            if isinstance(profile_data.get("general"), dict):
                latest_env = profile_data["general"].get("latest_env", {})
            elif "latest_env" in profile_data:
                latest_env = profile_data.get("latest_env", {})
            if thresh_key in latest_env:
                current_reading = latest_env[thresh_key]
            elif thresh_key.endswith("_ppm"):
                alt_key = thresh_key[:-4]
                if alt_key in latest_env:
                    current_reading = latest_env[alt_key]
            if current_reading is None and (thresh_key.lower() == "ec" or thresh_key.lower() == "ec_min"):
                if "ec" in latest_env:
                    current_reading = latest_env["ec"]
                elif "EC" in latest_env:
                    current_reading = latest_env["EC"]
        if current_reading is None:
            _LOGGER.error("No current reading for %s available for plant_id %s.", thresh_key, plant_id)
            # Continue checking other nutrients even if this one is not available
            continue

        # Convert current reading to float
        try:
            current_val = float(current_reading)
        except (TypeError, ValueError):
            _LOGGER.error("Current value for %s is invalid for plant_id %s: %s", thresh_key, plant_id, current_reading)
            continue
        # Convert threshold to float (use first element if it's a range list/tuple)
        try:
            threshold_val = float(thresh_value[0]) if isinstance(thresh_value, (list, tuple)) else float(thresh_value)
        except (TypeError, ValueError):
            _LOGGER.error("Threshold value for %s is invalid for plant_id %s: %s", thresh_key, plant_id, thresh_value)
            continue

        # Compare the current value against the threshold
        if current_val < threshold_val:
            # Format threshold name for logging (human-readable)
            thresh_name_str = str(thresh_key)
            # Replace underscores with spaces and remove unit annotations for readability
            thresh_name_str = thresh_name_str.replace("_", " ")
            if thresh_name_str.endswith(" ppm"):
                thresh_name_str = thresh_name_str[:-4]
            if thresh_name_str.endswith(" pct") or thresh_name_str.endswith(" percent"):
                if thresh_name_str.endswith(" pct"):
                    thresh_name_str = thresh_name_str[:-4]
                else:
                    thresh_name_str = thresh_name_str.rsplit(" ", 1)[0]
            # Capitalize first letter (the rest of the nutrient name remains lower case)
            thresh_name_str = thresh_name_str.capitalize()
            # Special-case acronym formatting for EC
            if thresh_key.lower().startswith("ec"):
                thresh_name_str = "EC"
            _LOGGER.info("%s below threshold for plant_id %s (%.2f < %.2f). Triggering fertilization.",
                         thresh_name_str, plant_id, current_val, threshold_val)
            return True

    # If we reach here, no nutrient was below its threshold
    _LOGGER.info("All monitored nutrient levels are within thresholds for plant_id %s. No fertilization needed.", plant_id)
    return False