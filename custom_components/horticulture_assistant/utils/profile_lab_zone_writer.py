import os
import json
import logging
from pathlib import Path

_LOGGER = logging.getLogger(__name__)

def generate_lab_zone_profiles(plant_id: str, base_path: str = None, overwrite: bool = False) -> str:
    """
    Create or update lab analysis log and zone calendar files for a plant profile.

    This function scaffolds two JSON files (`lab_analysis_log.json` and `zone_calendar.json`)
    in the `plants/<plant_id>/` directory.

    `lab_analysis_log.json` is initialized as an empty list. Each future entry in this log should be a dictionary with keys:
    "timestamp", "sample_type" (e.g., leaf, water, media), "lab_name", "results" (dict), "units" (dict), "detection_limits" (optional), and "notes".

    `zone_calendar.json` is initialized as a dictionary containing keys for USDA hardiness zones (e.g., "6a", "10b"). 
    Each zone key maps to a dictionary of cultural recommendations:
    "seeding_months", "transplant_months", "expected_harvest_months", "frost_risk_months", "critical_stress_windows".
    All values in this zone mapping default to null (JSON null, represented as None in Python).

    If a file already exists and `overwrite` is False, the file is left unchanged (skipped).
    If `overwrite` is True or the file is missing, a new file is created (or an existing file overwritten) with the default structure.

    All actions (creation, skipping, overwriting) are logged.

    :param plant_id: Identifier for the plant (used as directory name under the base path).
    :param base_path: Optional base directory path for plant profiles (defaults to "plants/" in current working directory).
    :param overwrite: If True, overwrite existing files; if False, skip writing if files already exist.
    :return: The plant_id if files were successfully created or already existed (skipped without error), or an empty string on error.
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

    # Define default content for each file
    lab_log_data = []  # empty list for lab_analysis_log
    zone_calendar_data = {}
    # Populate dictionary with all USDA hardiness zones (1a through 13b)
    for i in range(1, 14):
        for suffix in ["a", "b"]:
            zone_key = f"{i}{suffix}"
            zone_calendar_data[zone_key] = {
                "seeding_months": None,
                "transplant_months": None,
                "expected_harvest_months": None,
                "frost_risk_months": None,
                "critical_stress_windows": None
            }

    file_sections = {
        "lab_analysis_log.json": lab_log_data,
        "zone_calendar.json": zone_calendar_data
    }

    for filename, default_content in file_sections.items():
        file_path = plant_dir / filename
        if file_path.exists() and not overwrite:
            # Skip writing and log entry count if applicable
            entry_count = None
            try:
                with open(file_path, "r", encoding="utf-8") as existing_file:
                    existing_data = json.load(existing_file)
                    if isinstance(existing_data, list):
                        entry_count = len(existing_data)
            except Exception as e:
                _LOGGER.warning("Failed to read existing file %s: %s", file_path, e)
            if entry_count is not None:
                _LOGGER.info("File %s already exists with %d entries. Skipping write.", file_path, entry_count)
            else:
                _LOGGER.info("File %s already exists. Skipping write.", file_path)
            continue

        # Write new file or overwrite existing file with default content
        existed_before = file_path.exists()
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(default_content, f, indent=2)
            if existed_before and overwrite:
                _LOGGER.info("Overwrote existing file: %s", file_path)
            else:
                _LOGGER.info("Created file: %s", file_path)
        except Exception as e:
            _LOGGER.error("Failed to write %s: %s", file_path, e)
    _LOGGER.info("Lab analysis log and zone calendar prepared for '%s' at %s", plant_id, plant_dir)
    return plant_id