# File: custom_components/horticulture_assistant/utils/profile_sensor_log_writer.py

import logging
import json
import os

_LOGGER = logging.getLogger(__name__)

def scaffold_profile_files(plant_id: str, base_path: str = None, overwrite: bool = False) -> None:
    """Create sensor_reading_log.json and alert_event_log.json for a given plant's profile directory.
    
    This scaffolds a directory under the base_path (defaults to "plants") named after the plant_id,
    and creates two JSON files within it: "sensor_reading_log.json" and "alert_event_log.json".
    The sensor_reading_log.json file is initialized as an empty list intended to hold sensor reading entries.
    Each sensor reading entry will be a dictionary with fields such as "timestamp", "sensor_type", "value", 
    "unit", "source", "zone", and "notes". The alert_event_log.json file is initialized as an empty list 
    intended to hold alert event entries. Each alert event entry will be a dictionary with fields such as 
    "timestamp", "alert_type", "trigger_condition", "sensor_source", "resolved", "resolution_timestamp", 
    "user_acknowledged", and "notes".
    If a file already exists and overwrite is False, the file is left unchanged.
    Set overwrite=True to replace any existing files with the default structure (empty list).
    Logs messages for each created file, any skipped creations (including current entry count if applicable), 
    and any overwrite or error events encountered.
    """
    base_dir = base_path or "plants"
    plant_dir = os.path.join(base_dir, str(plant_id))
    # Ensure the plant directory exists
    try:
        os.makedirs(plant_dir, exist_ok=True)
    except Exception as e:
        _LOGGER.error("Failed to create directory %s for plant profile: %s", plant_dir, e)
        return
    
    # Default log structures (empty lists for log files)
    sensor_readings = []  # list for sensor reading log entries
    alert_events = []     # list for alert event log entries
    
    # File paths
    reading_log_file = os.path.join(plant_dir, "sensor_reading_log.json")
    alert_log_file = os.path.join(plant_dir, "alert_event_log.json")
    
    # Write or skip sensor_reading_log.json
    if not overwrite and os.path.isfile(reading_log_file):
        # File exists and not overwriting: log skip and current entry count
        entry_count = None
        try:
            with open(reading_log_file, "r", encoding="utf-8") as f:
                existing_data = json.load(f)
                if isinstance(existing_data, list):
                    entry_count = len(existing_data)
        except Exception as e:
            _LOGGER.warning("Failed to read existing sensor reading log at %s for counting entries: %s", reading_log_file, e)
        if entry_count is not None:
            _LOGGER.info("Sensor reading log already exists at %s with %d entries; skipping (overwrite=False).", reading_log_file, entry_count)
        else:
            _LOGGER.info("Sensor reading log already exists at %s; skipping (overwrite=False).", reading_log_file)
    else:
        if overwrite and os.path.isfile(reading_log_file):
            _LOGGER.info("Existing sensor reading log at %s will be overwritten.", reading_log_file)
        try:
            with open(reading_log_file, "w", encoding="utf-8") as f:
                json.dump(sensor_readings, f, indent=2)
            _LOGGER.info("Sensor reading log created for plant %s at %s", plant_id, reading_log_file)
        except Exception as e:
            _LOGGER.error("Failed to write sensor reading log for plant %s: %s", plant_id, e)
    
    # Write or skip alert_event_log.json
    if not overwrite and os.path.isfile(alert_log_file):
        # File exists and not overwriting: log skip and current entry count
        entry_count = None
        try:
            with open(alert_log_file, "r", encoding="utf-8") as f:
                existing_data = json.load(f)
                if isinstance(existing_data, list):
                    entry_count = len(existing_data)
        except Exception as e:
            _LOGGER.warning("Failed to read existing alert event log at %s for counting entries: %s", alert_log_file, e)
        if entry_count is not None:
            _LOGGER.info("Alert event log already exists at %s with %d entries; skipping (overwrite=False).", alert_log_file, entry_count)
        else:
            _LOGGER.info("Alert event log already exists at %s; skipping (overwrite=False).", alert_log_file)
    else:
        if overwrite and os.path.isfile(alert_log_file):
            _LOGGER.info("Existing alert event log at %s will be overwritten.", alert_log_file)
        try:
            with open(alert_log_file, "w", encoding="utf-8") as f:
                json.dump(alert_events, f, indent=2)
            _LOGGER.info("Alert event log created for plant %s at %s", plant_id, alert_log_file)
        except Exception as e:
            _LOGGER.error("Failed to write alert event log for plant %s: %s", plant_id, e)