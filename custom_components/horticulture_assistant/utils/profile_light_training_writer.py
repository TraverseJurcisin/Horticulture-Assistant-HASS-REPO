import logging
import json
import os

_LOGGER = logging.getLogger(__name__)

def scaffold_profile_files(plant_id: str, base_path: str = None, overwrite: bool = False) -> None:
    """
    Create light cycle and training/pruning log files for a given plant's profile directory.
    
    This scaffolds a directory under the base_path (defaults to "plants") named after the plant_id,
    and creates two JSON files within it: "light_cycle_log.json" and "training_pruning_log.json".
    The light_cycle_log.json file is initialized as an empty list intended to hold lighting cycle entries.
    Each light cycle entry is a dictionary with fields such as "timestamp", "light_type" (e.g., "LED", "HPS", "natural"),
    "hours_on", "DLI", "spectrum_target", "start_time", "end_time", and "notes". The training_pruning_log.json file is 
    initialized as an empty list intended to hold training and pruning entries. Each training/pruning entry includes fields 
    like "timestamp", "action_type" (e.g., "topping", "defoliation", "LST"), "performed_by", "tool_used", "plant_section", 
    "reason", and "notes".
    
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
    
    # Default empty structures for light cycle and training/pruning logs
    light_cycle_data = []
    training_pruning_data = []
    
    # File paths
    light_log_file = os.path.join(plant_dir, "light_cycle_log.json")
    training_log_file = os.path.join(plant_dir, "training_pruning_log.json")
    
    # Write or skip light_cycle_log.json
    if not overwrite and os.path.isfile(light_log_file):
        entry_count = None
        try:
            with open(light_log_file, "r", encoding="utf-8") as f:
                existing_data = json.load(f)
                if isinstance(existing_data, list):
                    entry_count = len(existing_data)
        except Exception as e:
            _LOGGER.warning("Failed to read existing light cycle log at %s for counting entries: %s", light_log_file, e)
        if entry_count is not None:
            _LOGGER.info("Light cycle log already exists at %s with %d entries; skipping (overwrite=False).", light_log_file, entry_count)
        else:
            _LOGGER.info("Light cycle log already exists at %s; skipping (overwrite=False).", light_log_file)
    else:
        if overwrite and os.path.isfile(light_log_file):
            _LOGGER.info("Existing light cycle log at %s will be overwritten.", light_log_file)
        try:
            with open(light_log_file, "w", encoding="utf-8") as f:
                json.dump(light_cycle_data, f, indent=2)
            _LOGGER.info("Light cycle log created for plant %s at %s", plant_id, light_log_file)
        except Exception as e:
            _LOGGER.error("Failed to write light cycle log for plant %s: %s", plant_id, e)
    
    # Write or skip training_pruning_log.json
    if not overwrite and os.path.isfile(training_log_file):
        entry_count = None
        try:
            with open(training_log_file, "r", encoding="utf-8") as f:
                existing_data = json.load(f)
                if isinstance(existing_data, list):
                    entry_count = len(existing_data)
        except Exception as e:
            _LOGGER.warning("Failed to read existing training/pruning log at %s for counting entries: %s", training_log_file, e)
        if entry_count is not None:
            _LOGGER.info("Training/pruning log already exists at %s with %d entries; skipping (overwrite=False).", training_log_file, entry_count)
        else:
            _LOGGER.info("Training/pruning log already exists at %s; skipping (overwrite=False).", training_log_file)
    else:
        if overwrite and os.path.isfile(training_log_file):
            _LOGGER.info("Existing training/pruning log at %s will be overwritten.", training_log_file)
        try:
            with open(training_log_file, "w", encoding="utf-8") as f:
                json.dump(training_pruning_data, f, indent=2)
            _LOGGER.info("Training/pruning log created for plant %s at %s", plant_id, training_log_file)
        except Exception as e:
            _LOGGER.error("Failed to write training/pruning log for plant %s: %s", plant_id, e)