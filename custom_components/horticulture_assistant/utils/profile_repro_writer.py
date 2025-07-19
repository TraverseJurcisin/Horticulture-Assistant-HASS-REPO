import os
import json
import logging
from pathlib import Path

_LOGGER = logging.getLogger(__name__)

def generate_reproductive_profiles(plant_id: str, base_dir: str = None, overwrite: bool = False) -> str:
    """
    Generate or update reproductive and phenology profile files for a given plant.

    This function scaffolds two JSON files (`reproductive.json` and `phenology.json`) in the `plants/<plant_id>/` directory.
    It populates these files with predefined keys related to the plant's reproductive and phenological information,
    with all values defaulting to null (JSON null, represented as None in Python).

    If a file already exists and `overwrite` is False, the file is left unchanged.
    If `overwrite` is True or the file is missing, a new file is created (or an existing file is overwritten) with the default structure.

    All actions (creation, skipping, overwriting) are logged for clarity.

    :param plant_id: Identifier for the plant (used as directory name under the base path).
    :param base_dir: Optional base directory path for plant profiles (defaults to "plants/" in the current working directory).
    :param overwrite: If True, overwrite existing files; if False, skip writing if files already exist.
    :return: The plant_id if profiles were successfully generated (or already present without changes),
             or an empty string on error (e.g., if directory creation fails).
    """
    # Determine base directory for plant profiles
    if base_dir:
        base_path = Path(base_dir)
    else:
        base_path = Path("plants")
    plant_dir = base_path / plant_id

    # Ensure the plant directory exists
    try:
        os.makedirs(plant_dir, exist_ok=True)
    except Exception as e:
        _LOGGER.error("Failed to create directory %s: %s", plant_dir, e)
        return ""

    # Define default content for reproductive.json
    reproductive_data = {
        "pollination_type": None,
        "flowering_triggers": {
            "temperature": None,
            "photoperiod": None,
            "nutrient": None
        },
        "fruit_development": None,
        "harvest_readiness": None,
        "self_pruning": None,
        "flower_to_fruit_rate": None
    }

    # Define default content for phenology.json
    phenology_data = {
        "flowering_period": None,
        "fruiting_period": None,
        "dormancy_triggers": None,
        "stage_by_zone_estimates": None,
        "chill_hour_needs": None
    }

    profile_sections = {
        "reproductive.json": reproductive_data,
        "phenology.json": phenology_data
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

    _LOGGER.info("Reproductive and phenology profiles prepared for '%s' at %s", plant_id, plant_dir)
    return plant_id