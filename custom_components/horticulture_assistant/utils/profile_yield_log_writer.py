import logging
import json
import os

_LOGGER = logging.getLogger(__name__)

def scaffold_profile_files(plant_id: str, base_path: str = None, overwrite: bool = False) -> None:
    """
    Create yield tracking and harvest weight log files for a given plant's profile directory.

    This scaffolds a directory under the base_path (defaults to "plants") named after the plant_id,
    and creates two JSON files within it: "yield_tracking_log.json" and "harvest_weight_log.json".
    Each file is initialized as an empty list. If a file already exists and overwrite is False,
    the file is left unchanged (with a log message including the existing entry count).
    Set overwrite=True to replace any existing files with the default (empty list) structure.
    Logs messages for each created file, any skipped creations (with entry count), and any errors encountered.
    """
    base_dir = base_path or "plants"
    plant_dir = os.path.join(base_dir, str(plant_id))
    # Ensure the plant directory exists
    try:
        os.makedirs(plant_dir, exist_ok=True)
    except Exception as e:
        _LOGGER.error("Failed to create directory %s for plant profile: %s", plant_dir, e)
        return

    # Default empty structures for yield tracking and harvest weight logs
    yield_data = []
    harvest_data = []

    # File paths
    yield_file = os.path.join(plant_dir, "yield_tracking_log.json")
    weight_file = os.path.join(plant_dir, "harvest_weight_log.json")

    # Write or skip yield_tracking_log.json
    if not overwrite and os.path.isfile(yield_file):
        try:
            with open(yield_file, "r", encoding="utf-8") as f:
                existing_data = json.load(f)
            entry_count = len(existing_data) if isinstance(existing_data, list) else 0
        except Exception as e:
            _LOGGER.error("Failed to read existing yield tracking log for plant %s at %s: %s", plant_id, yield_file, e)
            entry_count = 0
        _LOGGER.info("Yield tracking log already exists at %s with %d entries; skipping (overwrite=False).", yield_file, entry_count)
    else:
        try:
            with open(yield_file, "w", encoding="utf-8") as f:
                json.dump(yield_data, f, indent=2)
            _LOGGER.info("Yield tracking log created for plant %s at %s", plant_id, yield_file)
        except Exception as e:
            _LOGGER.error("Failed to write yield tracking log for plant %s: %s", plant_id, e)

    # Write or skip harvest_weight_log.json
    if not overwrite and os.path.isfile(weight_file):
        try:
            with open(weight_file, "r", encoding="utf-8") as f:
                existing_data = json.load(f)
            entry_count = len(existing_data) if isinstance(existing_data, list) else 0
        except Exception as e:
            _LOGGER.error("Failed to read existing harvest weight log for plant %s at %s: %s", plant_id, weight_file, e)
            entry_count = 0
        _LOGGER.info("Harvest weight log already exists at %s with %d entries; skipping (overwrite=False).", weight_file, entry_count)
    else:
        try:
            with open(weight_file, "w", encoding="utf-8") as f:
                json.dump(harvest_data, f, indent=2)
            _LOGGER.info("Harvest weight log created for plant %s at %s", plant_id, weight_file)
        except Exception as e:
            _LOGGER.error("Failed to write harvest weight log for plant %s: %s", plant_id, e)