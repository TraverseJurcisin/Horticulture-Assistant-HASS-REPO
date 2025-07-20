# File: custom_components/horticulture_assistant/utils/profile_postharvest_writer.py

import logging
import json
import os

_LOGGER = logging.getLogger(__name__)

def scaffold_profile_files(plant_id: str, base_path: str = None, overwrite: bool = False) -> None:
    """Create drying_log.json and curing_log.json for a given plant's profile directory.
    
    This scaffolds a directory under the base_path (defaults to "plants") named after the plant_id,
    and creates two JSON files within it: "drying_log.json" and "curing_log.json".
    Each file is initialized as an empty list to which drying or curing events can be appended.
    Each drying log entry includes timestamp, method (e.g., rack, oven, freeze-dry), start_moisture_pct,
    target_moisture_pct, temp_range_C, RH_range_pct, airflow_rate_cfm, duration_hrs, observed_outcome, and notes.
    Each curing log entry includes timestamp, method (e.g., burp, vacuum, sealed humidistat), container_type,
    duration_days, CO₂_release_events, final_moisture_pct, aroma_score, user_rating, and notes.
    If a file already exists and overwrite is False, the file is left unchanged.
    Set overwrite=True to replace any existing files (this will reset any existing log entries).
    Logs messages for each created file, any skipped creations (with existing entry counts if applicable), and any errors encountered.
    """
    base_dir = base_path or "plants"
    plant_dir = os.path.join(base_dir, str(plant_id))
    # Ensure the plant directory exists
    try:
        os.makedirs(plant_dir, exist_ok=True)
    except Exception as e:
        _LOGGER.error("Failed to create directory %s for plant profile: %s", plant_dir, e)
        return
    
    # Default log structures: empty lists
    drying_data = []
    curing_data = []
    
    # File paths
    dry_file = os.path.join(plant_dir, "drying_log.json")
    cur_file = os.path.join(plant_dir, "curing_log.json")
    
    # Handle drying_log.json
    dry_existed = os.path.isfile(dry_file)
    if dry_existed and not overwrite:
        # File exists and we are not allowed to overwrite, skip creation
        entry_count = None
        try:
            with open(dry_file, "r", encoding="utf-8") as f:
                existing_data = json.load(f)
            if isinstance(existing_data, list):
                entry_count = len(existing_data)
        except Exception as e:
            _LOGGER.warning("Could not read existing drying log at %s to count entries: %s", dry_file, e)
        if entry_count is not None:
            _LOGGER.info("Drying log file already exists at %s with %d entries; skipping (overwrite=False).", dry_file, entry_count)
        else:
            _LOGGER.info("Drying log file already exists at %s; skipping (overwrite=False).", dry_file)
    else:
        prev_count = None
        if dry_existed:
            # If file existed and will be overwritten, capture previous entry count
            try:
                with open(dry_file, "r", encoding="utf-8") as f:
                    existing_data = json.load(f)
                if isinstance(existing_data, list):
                    prev_count = len(existing_data)
            except Exception as e:
                _LOGGER.warning("Could not read existing drying log at %s to count entries before overwrite: %s", dry_file, e)
        try:
            with open(dry_file, "w", encoding="utf-8") as f:
                json.dump(drying_data, f, indent=2)
            if dry_existed:
                # File was overwritten
                if prev_count is not None:
                    _LOGGER.info("Drying log for plant %s at %s overwritten (previous entries: %d).", plant_id, dry_file, prev_count)
                else:
                    _LOGGER.info("Drying log for plant %s at %s overwritten.", plant_id, dry_file)
            else:
                # File did not exist before, so it was created
                _LOGGER.info("Drying log created for plant %s at %s", plant_id, dry_file)
        except Exception as e:
            _LOGGER.error("Failed to write drying log for plant %s: %s", plant_id, e)
    
    # Handle curing_log.json
    cur_existed = os.path.isfile(cur_file)
    if cur_existed and not overwrite:
        entry_count = None
        try:
            with open(cur_file, "r", encoding="utf-8") as f:
                existing_data = json.load(f)
            if isinstance(existing_data, list):
                entry_count = len(existing_data)
        except Exception as e:
            _LOGGER.warning("Could not read existing curing log at %s to count entries: %s", cur_file, e)
        if entry_count is not None:
            _LOGGER.info("Curing log file already exists at %s with %d entries; skipping (overwrite=False).", cur_file, entry_count)
        else:
            _LOGGER.info("Curing log file already exists at %s; skipping (overwrite=False).", cur_file)
    else:
        prev_count = None
        if cur_existed:
            try:
                with open(cur_file, "r", encoding="utf-8") as f:
                    existing_data = json.load(f)
                if isinstance(existing_data, list):
                    prev_count = len(existing_data)
            except Exception as e:
                _LOGGER.warning("Could not read existing curing log at %s to count entries before overwrite: %s", cur_file, e)
        try:
            with open(cur_file, "w", encoding="utf-8") as f:
                json.dump(curing_data, f, indent=2)
            if cur_existed:
                if prev_count is not None:
                    _LOGGER.info("Curing log for plant %s at %s overwritten (previous entries: %d).", plant_id, cur_file, prev_count)
                else:
                    _LOGGER.info("Curing log for plant %s at %s overwritten.", plant_id, cur_file)
            else:
                _LOGGER.info("Curing log created for plant %s at %s", plant_id, cur_file)
        except Exception as e:
            _LOGGER.error("Failed to write curing log for plant %s: %s", plant_id, e)