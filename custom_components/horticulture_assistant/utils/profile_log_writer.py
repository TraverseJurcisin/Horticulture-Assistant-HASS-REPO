import os
import json
import logging
from pathlib import Path

_LOGGER = logging.getLogger(__name__)

def generate_profile_logs(plant_id: str, base_path: str = None, overwrite: bool = False) -> str:
    """
    Create or update log files (pest scouting and irrigation) for a plant profile.

    This function scaffolds two JSON files (`pest_scouting_log.json` and `irrigation_log.json`)
    in the `plants/<plant_id>/` directory. These files are initialized as empty lists, intended to hold log entries.

    Each entry in `pest_scouting_log.json` should be a dictionary with keys:
    "timestamp", "observer", "pest_type", "severity", "location", "notes".
    Each entry in `irrigation_log.json` should be a dictionary with keys:
    "timestamp", "volume_applied_ml", "method", "source", "zone_targeted", "success", "notes".

    If a file already exists and `overwrite` is False, the file is left unchanged.
    If `overwrite` is True or the file is missing, a new file is created (or an existing file overwritten) with an empty list.

    If an existing file is not overwritten and contains a list, the length of the list (number of entries) is logged.

    All actions (creation, skipping, overwriting) are logged.

    :param plant_id: Identifier for the plant (used as directory name under the base path).
    :param base_path: Optional base directory path for plant profiles (defaults to "plants/" in current working directory).
    :param overwrite: If True, overwrite existing log files; if False, skip writing if files already exist.
    :return: The plant_id if logs were successfully created or already existed (skipped), or an empty string on error.
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
        return ""
    # Define default (empty list) content for each log file
    log_sections = {
        "pest_scouting_log.json": [],
        "irrigation_log.json": []
    }
    # Create or skip each log file
    for filename, default_content in log_sections.items():
        file_path = plant_dir / filename
        if file_path.exists() and not overwrite:
            try:
                with open(file_path, "r", encoding="utf-8") as existing_file:
                    existing_data = json.load(existing_file)
                if isinstance(existing_data, list):
                    _LOGGER.info("File %s already exists with %d entries. Skipping write.", file_path, len(existing_data))
                else:
                    _LOGGER.info("File %s already exists. Skipping write.", file_path)
            except Exception as e:
                _LOGGER.error("Failed to read existing file %s: %s", file_path, e)
                _LOGGER.info("File %s already exists. Skipping write.", file_path)
            continue
        # Write new or overwrite existing log file with default content
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(default_content, f, indent=2)
            if file_path.exists() and overwrite:
                _LOGGER.info("Overwrote existing file: %s", file_path)
            else:
                _LOGGER.info("Created file: %s", file_path)
        except Exception as e:
            _LOGGER.error("Failed to write %s: %s", file_path, e)
    _LOGGER.info("Pest scouting and irrigation logs prepared for '%s' at %s", plant_id, plant_dir)
    return plant_id