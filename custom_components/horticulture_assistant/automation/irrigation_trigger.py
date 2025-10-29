"""Simplified irrigation trigger helper."""

from __future__ import annotations

import logging
from pathlib import Path

from custom_components.horticulture_assistant.utils.path_utils import plants_path
from plant_engine.utils import load_json

_LOGGER = logging.getLogger(__name__)


def irrigation_trigger(plant_id: str, base_path: str | None = None, sensor_data: dict | None = None) -> bool:
    """
    Determine whether to trigger irrigation for a given plant based on soil moisture.
    Args:
        plant_id: Identifier of the plant profile.
        base_path: Base directory path where plant profiles are stored. Defaults
            to the configured ``plants`` directory.
        sensor_data: Dictionary of current sensor readings (keys like 'soil_moisture', 'EC', 'temp', etc).
    Returns:
        True if irrigation should be triggered, False otherwise.
    """
    if base_path is None:
        base_path = plants_path(None)
    if sensor_data is None:
        sensor_data = {}
    # Load plant profile from JSON file
    profile_path = Path(base_path) / f"{plant_id}.json"
    if not profile_path.is_file():
        _LOGGER.error("Plant profile file not found for plant_id: %s", plant_id)
        return False
    try:
        profile_data = load_json(str(profile_path))
    except Exception as exc:  # pragma: no cover - log and fail gracefully
        _LOGGER.error("Failed to load profile for plant_id %s: %s", plant_id, exc)
        return False

    # Check if irrigation is globally enabled for this plant
    irrigation_enabled = True
    # The profile may include a flag for irrigation in either 'actuators' or top-level keys
    if isinstance(profile_data.get("actuators"), dict):
        irrigation_enabled = profile_data["actuators"].get("irrigation_enabled", True)
    # Some profiles might use a top-level or 'general' flag for irrigation
    if (
        not irrigation_enabled
        or profile_data.get("irrigation_enabled") is False
        or (
            isinstance(profile_data.get("general"), dict) and profile_data["general"].get("irrigation_enabled") is False
        )
    ):
        _LOGGER.info(
            "Irrigation is disabled in the profile for plant_id %s. Skipping irrigation trigger check.",
            plant_id,
        )
        return False

    # Determine the soil moisture threshold
    thresholds = profile_data.get("thresholds", {})
    threshold_value = None
    if "soil_moisture_min" in thresholds:
        threshold_value = thresholds["soil_moisture_min"]
    elif "soil_moisture_pct" in thresholds:
        # If only a single percentage threshold is given, treat it as the minimum required.
        threshold_value = thresholds["soil_moisture_pct"]
    elif "soil_moisture" in thresholds:
        threshold_value = thresholds["soil_moisture"]
    else:
        _LOGGER.error("No soil moisture threshold found in profile for plant_id %s.", plant_id)
        return False

    # Get current soil moisture from sensor_data or profile (if available)
    current_moisture = None
    for key in ["soil_moisture", "soil_moisture_pct", "moisture", "vwc"]:
        if key in sensor_data:
            current_moisture = sensor_data[key]
            break
    # If not provided in sensor_data, check profile_data for a latest reading
    if current_moisture is None:
        latest_env = {}
        if isinstance(profile_data.get("general"), dict):
            latest_env = profile_data["general"].get("latest_env", {})
        elif "latest_env" in profile_data:
            latest_env = profile_data.get("latest_env", {})
        for key in ["soil_moisture", "soil_moisture_pct", "moisture", "vwc"]:
            if key in latest_env:
                current_moisture = latest_env[key]
                break
    if current_moisture is None:
        _LOGGER.error("No current soil moisture reading available for plant_id %s.", plant_id)
        return False

    # Convert readings to float for comparison
    try:
        current_val = float(current_moisture)
    except (TypeError, ValueError):
        _LOGGER.error(
            "Current soil moisture value is invalid for plant_id %s: %s",
            plant_id,
            current_moisture,
        )
        return False
    try:
        # If threshold is a list or tuple (range), use the first value as the minimum threshold
        threshold_val = (
            float(threshold_value[0]) if isinstance(threshold_value, list | tuple) else float(threshold_value)
        )
    except (TypeError, ValueError):
        _LOGGER.error(
            "Soil moisture threshold is invalid for plant_id %s: %s",
            plant_id,
            threshold_value,
        )
        return False

    # Compare the current moisture against the threshold
    if current_val < threshold_val:
        _LOGGER.info(
            "Soil moisture below threshold for plant_id %s (%.2f < %.2f). Triggering irrigation.",
            plant_id,
            current_val,
            threshold_val,
        )
        return True

    _LOGGER.info(
        "Soil moisture sufficient for plant_id %s (%.2f >= %.2f). No irrigation needed.",
        plant_id,
        current_val,
        threshold_val,
    )
    return False
