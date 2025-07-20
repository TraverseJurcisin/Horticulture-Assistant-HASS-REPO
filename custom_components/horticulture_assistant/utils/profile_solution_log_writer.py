import os
import json
import logging
from pathlib import Path

_LOGGER = logging.getLogger(__name__)

def initialize_solution_logs(plant_id: str, base_path: str = None, overwrite: bool = False) -> bool:
    """
    Initialize pH adjustment and recipe revision log files for a given plant profile.
    
    This function scaffolds two JSON files (`ph_adjustment_log.json` and `recipe_revision_log.json`)
    in the `plants/<plant_id>/` directory. These files are initialized as empty lists, intended to hold log entries.
    
    Each entry in `ph_adjustment_log.json` should be a dictionary with keys like:
    "timestamp", "solution_type", "starting_pH", "adjusted_pH", "agent_used", "amount_applied_ml", "reason", "person_responsible", "notes".
    Each entry in `recipe_revision_log.json` should be a dictionary with keys like:
    "timestamp", "previous_formula", "new_formula", "reason_for_change", "impacted_zones", "user_confirmed", "notes".
    
    If a file already exists and `overwrite` is False, the file is left unchanged.
    If `overwrite` is True or the file is missing, a new file is created (or an existing file overwritten) with an empty list.
    
    If an existing file is not overwritten and contains a list, the length of the list (number of entries) is logged.
    
    All actions (creation, skipping, overwriting) are logged.
    
    :param plant_id: Identifier for the plant (used as directory name under the base path).
    :param base_path: Optional base directory path for plant profiles (defaults to "plants/" in the current working directory).
    :param overwrite: If True, overwrite existing log files; if False, skip writing if files already exist.
    :return: True if log files were successfully created or already existed (skipped) without errors, False if an error occurred (e.g., directory creation or file write failure).
    """
    # Determine base directory for plant profiles
    if base_path:
        base_dir = Path(base_path)
    else:
        base_dir = Path("plants")
    plant_dir = base_dir / str(plant_id)
    
    # Ensure the plant directory exists
    try:
        os.makedirs(plant_dir, exist_ok=True)
    except Exception as e:
        _LOGGER.error("Failed to create directory %s: %s", plant_dir, e)
        return False
    
    # List of log files to create
    log_files = ["ph_adjustment_log.json", "recipe_revision_log.json"]
    success = True
    # Iterate through each log file and create or skip as needed
    for filename in log_files:
        file_path = plant_dir / filename
        if file_path.exists() and not overwrite:
            # Skip creation if file already exists and not overwriting
            entry_count = None
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        entry_count = len(data)
            except Exception as e:
                _LOGGER.warning("Could not read %s to count entries: %s", file_path, e)
            if entry_count is not None:
                _LOGGER.info("File %s already exists with %d entries. Skipping creation.", file_path, entry_count)
            else:
                _LOGGER.info("File %s already exists. Skipping creation.", file_path)
            continue
        # Create or overwrite the file with an empty list
        existed_before = file_path.exists()
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump([], f, indent=2)
            if existed_before and overwrite:
                _LOGGER.info("Overwrote existing file: %s", file_path)
            else:
                _LOGGER.info("Created file: %s", file_path)
        except Exception as e:
            _LOGGER.error("Failed to write %s: %s", file_path, e)
            success = False
    if success:
        _LOGGER.info("pH adjustment and recipe revision logs prepared for '%s' at %s", plant_id, plant_dir)
    return success