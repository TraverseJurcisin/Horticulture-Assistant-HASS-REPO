import os
import json
import logging
from pathlib import Path

_LOGGER = logging.getLogger(__name__)

def generate_harvest_profiles(plant_id: str, base_dir: str = None, overwrite: bool = False) -> str:
    """
    Generate or update harvest and yield profile files for a given plant.

    This function scaffolds two JSON files (`harvest.json` and `yield.json`) in the `plants/<plant_id>/` directory.
    It populates these files with predefined keys related to the plant's harvesting and yield information,
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

    # Define default content for harvest.json
    harvest_data = {
        "harvest_timing": None,
        "indicators_of_ripeness": None,
        "harvesting_method": None,
        "postharvest_storage": None,
        "spoilage_rate": None,
        "market_channels": None
    }

    # Define default content for yield.json
    yield_data = {
        "expected_yield_range": None,
        "standard_yield_unit": None,
        "per_area_volume_metrics": {
            "per_acre": None,
            "per_cubic_ft": None,
            "per_gallon_media": None
        },
        "historical_yield": None,
        "yield_density_range": None,
        "projected_yield_model": None
    }

    profile_sections = {
        "harvest.json": harvest_data,
        "yield.json": yield_data
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

    _LOGGER.info("Harvest and yield profiles prepared for '%s' at %s", plant_id, plant_dir)
    return plant_id