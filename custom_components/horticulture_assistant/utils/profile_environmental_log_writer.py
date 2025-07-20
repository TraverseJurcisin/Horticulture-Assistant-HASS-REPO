import logging
import json
import os

_LOGGER = logging.getLogger(__name__)

def scaffold_profile_files(plant_id: str, base_path: str = None, overwrite: bool = False) -> None:
    """
    Create environmental incident and cultural disruption log files for a given plant's profile directory.

    This scaffolds a directory under the base_path (defaults to "plants") named after the plant_id,
    and creates two JSON files within it: "environmental_incident_log.json" and "cultural_disruption_log.json".
    The environmental_incident_log.json file is initialized as an empty list intended to hold incident events.
    Each incident entry is a dictionary with fields such as "timestamp", "event_type", "severity", "duration_estimate",
    "detection_method", "impact_area", "resolution_status", and "notes". The cultural_disruption_log.json file is also
    initialized as an empty list intended to log skipped cultural practices. Each entry includes fields like "timestamp",
    "practice_skipped", "reason", "duration_skipped_days", "observed_impact", "corrective_action_taken", and "notes".
    If a file already exists and overwrite is False, the file is left unchanged.
    Set overwrite=True to replace any existing files with the default (empty list) structure.
    Logs messages for each created file, any skipped creations (with entry count if available), and any overwrite or error events.
    """
    base_dir = base_path or "plants"
    plant_dir = os.path.join(base_dir, str(plant_id))
    # Ensure the plant directory exists
    try:
        os.makedirs(plant_dir, exist_ok=True)
    except Exception as e:
        _LOGGER.error("Failed to create directory %s for plant profile: %s", plant_dir, e)
        return

    # Default empty structures for environmental incident and cultural disruption logs
    environmental_data = []
    cultural_data = []

    # File paths
    env_log_file = os.path.join(plant_dir, "environmental_incident_log.json")
    cult_log_file = os.path.join(plant_dir, "cultural_disruption_log.json")

    # Write or skip environmental_incident_log.json
    if not overwrite and os.path.isfile(env_log_file):
        entry_count = None
        try:
            with open(env_log_file, "r", encoding="utf-8") as f:
                existing_data = json.load(f)
                if isinstance(existing_data, list):
                    entry_count = len(existing_data)
        except Exception as e:
            _LOGGER.warning("Failed to read existing environmental incident log at %s for counting entries: %s", env_log_file, e)
        if entry_count is not None:
            _LOGGER.info("Environmental incident log already exists at %s with %d entries; skipping (overwrite=False).", env_log_file, entry_count)
        else:
            _LOGGER.info("Environmental incident log already exists at %s; skipping (overwrite=False).", env_log_file)
    else:
        if overwrite and os.path.isfile(env_log_file):
            _LOGGER.info("Existing environmental incident log at %s will be overwritten.", env_log_file)
        try:
            with open(env_log_file, "w", encoding="utf-8") as f:
                json.dump(environmental_data, f, indent=2)
            _LOGGER.info("Environmental incident log created for plant %s at %s", plant_id, env_log_file)
        except Exception as e:
            _LOGGER.error("Failed to write environmental incident log for plant %s: %s", plant_id, e)

    # Write or skip cultural_disruption_log.json
    if not overwrite and os.path.isfile(cult_log_file):
        entry_count = None
        try:
            with open(cult_log_file, "r", encoding="utf-8") as f:
                existing_data = json.load(f)
                if isinstance(existing_data, list):
                    entry_count = len(existing_data)
        except Exception as e:
            _LOGGER.warning("Failed to read existing cultural disruption log at %s for counting entries: %s", cult_log_file, e)
        if entry_count is not None:
            _LOGGER.info("Cultural disruption log already exists at %s with %d entries; skipping (overwrite=False).", cult_log_file, entry_count)
        else:
            _LOGGER.info("Cultural disruption log already exists at %s; skipping (overwrite=False).", cult_log_file)
    else:
        if overwrite and os.path.isfile(cult_log_file):
            _LOGGER.info("Existing cultural disruption log at %s will be overwritten.", cult_log_file)
        try:
            with open(cult_log_file, "w", encoding="utf-8") as f:
                json.dump(cultural_data, f, indent=2)
            _LOGGER.info("Cultural disruption log created for plant %s at %s", plant_id, cult_log_file)
        except Exception as e:
            _LOGGER.error("Failed to write cultural disruption log for plant %s: %s", plant_id, e)