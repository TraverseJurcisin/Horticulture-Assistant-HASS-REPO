import logging
import json
import os

_LOGGER = logging.getLogger(__name__)

def scaffold_profile_files(plant_id: str, base_path: str = None, overwrite: bool = False) -> None:
    """Create visual inspection and stress response log files for a given plant's profile directory.
    
    This scaffolds a directory under the base_path (defaults to "plants") named after the plant_id,
    and creates two JSON files within it: "visual_inspection_log.json" and "stress_response_log.json".
    The visual_inspection_log.json file is initialized as an empty list intended to hold visual inspection entries.
    Each visual inspection entry is a dictionary with fields such as "timestamp", "inspector_name", "observation_area"
    (e.g., "canopy", "root zone", "media surface"), "health_status" (visual assessment), "anomalies_detected",
    "photographic_reference" (URL or path), and "notes". The stress_response_log.json file is initialized as an 
    empty list intended to hold stress response entries. Each stress response entry includes fields like "timestamp",
    "stressor_type" (e.g., "light", "heat", "cold", "pest", "nutrient"), "affected_parts", "visible_symptoms",
    "severity_score" (1–5 scale), "recovery_observed", and "notes".
    
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
    
    # Default log structures (empty lists for log files)
    visual_data = []    # list for visual inspection log entries
    stress_data = []    # list for stress response log entries
    
    # File paths
    visual_log_file = os.path.join(plant_dir, "visual_inspection_log.json")
    stress_log_file = os.path.join(plant_dir, "stress_response_log.json")
    
    # Write or skip visual_inspection_log.json
    if not overwrite and os.path.isfile(visual_log_file):
        # File exists and not overwriting: log skip and current entry count if possible
        entry_count = None
        try:
            with open(visual_log_file, "r", encoding="utf-8") as f:
                existing_data = json.load(f)
                if isinstance(existing_data, list):
                    entry_count = len(existing_data)
        except Exception as e:
            _LOGGER.warning("Failed to read existing visual inspection log at %s for counting entries: %s", visual_log_file, e)
        if entry_count is not None:
            _LOGGER.info("Visual inspection log already exists at %s with %d entries; skipping (overwrite=False).", visual_log_file, entry_count)
        else:
            _LOGGER.info("Visual inspection log already exists at %s; skipping (overwrite=False).", visual_log_file)
    else:
        if overwrite and os.path.isfile(visual_log_file):
            _LOGGER.info("Existing visual inspection log at %s will be overwritten.", visual_log_file)
        try:
            with open(visual_log_file, "w", encoding="utf-8") as f:
                json.dump(visual_data, f, indent=2)
            _LOGGER.info("Visual inspection log created for plant %s at %s", plant_id, visual_log_file)
        except Exception as e:
            _LOGGER.error("Failed to write visual inspection log for plant %s: %s", plant_id, e)
    
    # Write or skip stress_response_log.json
    if not overwrite and os.path.isfile(stress_log_file):
        # File exists and not overwriting: log skip and current entry count if possible
        entry_count = None
        try:
            with open(stress_log_file, "r", encoding="utf-8") as f:
                existing_data = json.load(f)
                if isinstance(existing_data, list):
                    entry_count = len(existing_data)
        except Exception as e:
            _LOGGER.warning("Failed to read existing stress response log at %s for counting entries: %s", stress_log_file, e)
        if entry_count is not None:
            _LOGGER.info("Stress response log already exists at %s with %d entries; skipping (overwrite=False).", stress_log_file, entry_count)
        else:
            _LOGGER.info("Stress response log already exists at %s; skipping (overwrite=False).", stress_log_file)
    else:
        if overwrite and os.path.isfile(stress_log_file):
            _LOGGER.info("Existing stress response log at %s will be overwritten.", stress_log_file)
        try:
            with open(stress_log_file, "w", encoding="utf-8") as f:
                json.dump(stress_data, f, indent=2)
            _LOGGER.info("Stress response log created for plant %s at %s", plant_id, stress_log_file)
        except Exception as e:
            _LOGGER.error("Failed to write stress response log for plant %s: %s", plant_id, e)