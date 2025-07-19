import os
import json
import logging
from pathlib import Path

_LOGGER = logging.getLogger(__name__)

def generate_stage_timing_profiles(plant_id: str, base_path: str = None, overwrite: bool = False) -> str:
    """
    Generate or update stage progress and calendar timing profile files for a given plant.

    This function scaffolds two JSON files (`stage_progress.json` and `calendar_timing.json`) in the `plants/<plant_id>/` directory.
    It populates these files with predefined keys related to the plant's life stage progress and per-zone calendar timing guidance,
    with all values defaulting to null (JSON null, represented as None in Python).

    If a file already exists and `overwrite` is False, the file is left unchanged.
    If `overwrite` is True or the file is missing, a new file is created (or an existing file is overwritten) with the default structure.

    All actions (creation, skipping, overwriting) are logged for clarity.

    :param plant_id: Identifier for the plant (used as directory name under the base path).
    :param base_path: Optional base directory path for plant profiles (defaults to "plants/" in the current working directory).
    :param overwrite: If True, overwrite existing files; if False, skip writing if files already exist.
    :return: The plant_id if profiles were successfully generated (or already present without changes),
             or an empty string on error (e.g., if directory creation fails).
    """
    # Determine base directory for plant profiles
    if base_path:
        base_dir = Path(base_path)
    else:
        base_dir = Path("plants")
    plant_dir = base_dir / plant_id

    # Ensure the plant directory exists
    try:
        os.makedirs(plant_dir, exist_ok=True)
    except Exception as e:
        _LOGGER.error("Failed to create directory %s: %s", plant_dir, e)
        return ""

    # Define default content for stage_progress.json
    stage_progress_data = {
        "observed_stage": None,
        "expected_stage": None,
        "last_transition_date": None,
        "next_expected_stage": None,
        "growth_rate_class": None,
        "current_duration_days": None
    }

    # Define default content for calendar_timing.json
    calendar_timing_data = {
        "zone_5a": {
            "seedling": None,
            "veg": None,
            "flower": None
        }
    }

    profile_sections = {
        "stage_progress.json": stage_progress_data,
        "calendar_timing.json": calendar_timing_data
    }

    # Write each profile section to its JSON file if needed
    for filename, data in profile_sections.items():
        file_path = plant_dir / filename
        if file_path.exists() and not overwrite:
            _LOGGER.info("File %s already exists. Skipping write.", file_path)
            continue
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            if file_path.exists() and overwrite:
                _LOGGER.info("Overwrote existing file: %s", file_path)
            else:
                _LOGGER.info("Created file: %s", file_path)
        except Exception as e:
            _LOGGER.error("Failed to write %s: %s", file_path, e)

    _LOGGER.info("Stage progress and calendar timing profiles prepared for '%s' at %s", plant_id, plant_dir)
    return plant_id