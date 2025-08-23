"""Automated nutrient management based on plant profile data."""

import logging
from datetime import datetime
from pathlib import Path

from custom_components.horticulture_assistant.utils.path_utils import plants_path

from .helpers import append_json_log, iter_profiles, latest_env

# Global override: disable automation if False
ENABLE_AUTOMATION = False

_LOGGER = logging.getLogger(__name__)


def run_fertilizer_cycle(base_path: str | None = None) -> None:
    """
    Run one cycle of automated fertilization checks for all plant profiles.
    Scans the plants directory for profile JSON files, checks nutrient levels
    against thresholds, and triggers fertilizer actuators if needed.

    ``base_path`` defaults to the configured ``plants`` directory.
    """
    # Global override check
    if not ENABLE_AUTOMATION:
        _LOGGER.info(
            "Automation is globally disabled (ENABLE_AUTOMATION=False). Skipping fertilization cycle."
        )
        return

    if base_path is None:
        base_path = plants_path(None)
    plants_dir = Path(base_path)
    if not plants_dir.is_dir():
        _LOGGER.error("Plants directory not found: %s", plants_dir)
        return

    profiles = iter_profiles(base_path)
    found = False

    for plant_id, profile_data in profiles:
        found = True

        # Check if fertilization is enabled for this plant
        fertilizer_enabled = True
        if isinstance(profile_data.get("actuators"), dict):
            fertilizer_enabled = profile_data["actuators"].get(
                "fertilizer_enabled", True
            )
        if (
            not fertilizer_enabled
            or profile_data.get("fertilizer_enabled") is False
            or (
                isinstance(profile_data.get("general"), dict)
                and profile_data["general"].get("fertilizer_enabled") is False
            )
        ):
            _LOGGER.info(
                "Fertilization is disabled in the profile for plant %s. Skipping fertilizer check.",
                plant_id,
            )
            continue

        # Get the latest sensor data for this plant (nutrient levels, EC, etc.)
        sensor_data = latest_env(profile_data)
        if not sensor_data:
            _LOGGER.warning(
                "No latest sensor data found for plant %s. Skipping.", plant_id
            )
            continue

        # Determine nutrient thresholds to check (exclude non-nutrient thresholds)
        thresholds = profile_data.get("thresholds", {})
        relevant_thresholds = {}
        if isinstance(thresholds, dict):
            for key, value in thresholds.items():
                k_lower = str(key).lower()
                # Skip thresholds for moisture, temperature, light, or known contaminants/heavy metals
                if "moisture" in k_lower or "temp" in k_lower or "light" in k_lower:
                    continue
                if (
                    "arsenic" in k_lower
                    or "cadmium" in k_lower
                    or "lead" in k_lower
                    or "mercury" in k_lower
                ):
                    continue
                if k_lower == "ph":
                    continue
                relevant_thresholds[key] = value
        if not relevant_thresholds:
            _LOGGER.error(
                "No nutrient thresholds found for plant %s. Skipping.", plant_id
            )
            continue

        # Check each nutrient threshold against current readings
        triggered = False
        reason_str = ""
        for thresh_key, thresh_value in relevant_thresholds.items():
            # Determine current reading for this threshold
            current_reading = None
            if thresh_key in sensor_data:
                current_reading = sensor_data[thresh_key]
            else:
                # Try alternative keys without units or common variants
                if str(thresh_key).endswith("_ppm"):
                    alt_key = thresh_key[:-4]  # remove "_ppm"
                    if alt_key in sensor_data:
                        current_reading = sensor_data[alt_key]
                if current_reading is None and (
                    thresh_key.lower() == "ec" or thresh_key.lower() == "ec_min"
                ):
                    # Check for EC (case-insensitive) in sensor_data keys
                    if "ec" in sensor_data:
                        current_reading = sensor_data["ec"]
                    elif "EC" in sensor_data:
                        current_reading = sensor_data["EC"]
            if current_reading is None:
                _LOGGER.error(
                    "No current reading for %s available for plant %s.",
                    thresh_key,
                    plant_id,
                )
                # Continue to next nutrient if this one has no data
                continue
            # Convert current reading to float
            try:
                current_val = float(current_reading)
            except (TypeError, ValueError):
                _LOGGER.error(
                    "Current value for %s is invalid for plant %s: %s",
                    thresh_key,
                    plant_id,
                    current_reading,
                )
                continue
            # Convert threshold to float (if list or tuple, use first element as minimum threshold)
            try:
                threshold_val = (
                    float(thresh_value[0])
                    if isinstance(thresh_value, list | tuple)
                    else float(thresh_value)
                )
            except (TypeError, ValueError):
                _LOGGER.error(
                    "Threshold value for %s is invalid for plant %s: %s",
                    thresh_key,
                    plant_id,
                    thresh_value,
                )
                continue

            # Compare the current value against the threshold
            if current_val < threshold_val:
                # Format threshold name for human-readable reason
                thresh_name_str = str(thresh_key).replace("_", " ")
                if thresh_name_str.endswith(" ppm"):
                    thresh_name_str = thresh_name_str[:-4]
                if thresh_name_str.endswith(" pct") or thresh_name_str.endswith(
                    " percent"
                ):
                    if thresh_name_str.endswith(" pct"):
                        thresh_name_str = thresh_name_str[:-4]
                    else:
                        thresh_name_str = thresh_name_str.rsplit(" ", 1)[0]
                # Capitalize first letter, special-case EC acronym
                thresh_name_str = thresh_name_str.capitalize()
                if thresh_key.lower().startswith("ec"):
                    thresh_name_str = "EC"
                _LOGGER.info(
                    "%s below threshold for plant %s (%.2f < %.2f). Triggering fertilization.",
                    thresh_name_str,
                    plant_id,
                    current_val,
                    threshold_val,
                )
                triggered = True
                reason_str = f"{thresh_name_str} below threshold"
                # Trigger the fertilizer actuator for this plant
                try:
                    from custom_components.horticulture_assistant.automation import (
                        fertilizer_actuator,
                    )

                    fertilizer_actuator.trigger_fertilizer_actuator(
                        plant_id=plant_id, trigger=True, base_path=base_path
                    )
                except Exception as e:
                    _LOGGER.error(
                        "Failed to trigger fertilizer actuator for plant %s: %s",
                        plant_id,
                        e,
                    )
                # Append a log entry to nutrient_application_log.json
                try:
                    log_file = (
                        plants_dir / str(plant_id) / "nutrient_application_log.json"
                    )
                    entry = {
                        "timestamp": datetime.now().isoformat(),
                        "reason": reason_str,
                        "triggered": True,
                        "source": "automation",
                    }
                    append_json_log(log_file, entry)
                except Exception as e:
                    _LOGGER.error(
                        "Failed to write nutrient application log for plant %s: %s",
                        plant_id,
                        e,
                    )
                # Only trigger once per cycle per plant (stop checking other nutrients after triggering)
                break

        if not triggered:
            _LOGGER.info(
                "All monitored nutrient levels are within thresholds for plant %s. No fertilization needed.",
                plant_id,
            )

    if not found:
        _LOGGER.info(
            "No plant profile JSON files found in %s. Nothing to do.", plants_dir
        )
