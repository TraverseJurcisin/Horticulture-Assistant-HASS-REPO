import os
import json
import logging
from pathlib import Path

_LOGGER = logging.getLogger(__name__)

def generate_stress_profiles(plant_id: str, base_path: str = None, overwrite: bool = False) -> str:
    """
    Generate or update pest resistance and stress tolerance profile files for a given plant.

    This function scaffolds two JSON files (`pest_resistance.json` and `stress_tolerance.json`) in the `plants/<plant_id>/` directory.
    It populates these files with predefined keys related to the plant's pest resistance and stress tolerance information,
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

    # Define default content for pest_resistance.json
    pest_resistance_data = {
        "known_pests": None,
        "pest_pressure_by_stage": None,
        "symptoms": None,
        "resistance_mechanisms": None,
        "pesticide_sensitivity": None,
        "pest_location_targeting": None
    }

    # Define default content for stress_tolerance.json
    stress_tolerance_data = {
        "drought": None,
        "salinity": None,
        "temperature_extremes": None,
        "compaction": None,
        "wind": None,
        "flooding": None,
        "frost": None,
        "pruning": None,
        "heavy_metal_tolerance": None
    }

    profile_sections = {
        "pest_resistance.json": pest_resistance_data,
        "stress_tolerance.json": stress_tolerance_data
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

    _LOGGER.info("Pest resistance and stress tolerance profiles prepared for '%s' at %s", plant_id, plant_dir)
    return plant_id