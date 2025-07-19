import logging
import json
import os

_LOGGER = logging.getLogger(__name__)

def scaffold_profile_files(plant_id: str, base_path: str = None, overwrite: bool = False) -> None:
    """
    Create storage.json and processing.json for a given plant's profile directory.

    This scaffolds a directory under the base_path (defaults to "plants") named after the plant_id,
    and creates two JSON files within it: "storage.json" and "processing.json".
    Each file contains preset fields relevant to post-harvest storage and processing, initialized to null values.
    If a file already exists and overwrite is False, the file is left unchanged.
    Set overwrite=True to replace any existing files with the default structure.
    Logs messages for each created file, any skipped creations, and any errors encountered.

    :param plant_id: Identifier for the plant (used as directory name under base_path).
    :param base_path: Base directory for plant profiles (defaults to "plants" in current working directory).
    :param overwrite: If True, overwrite existing files; if False, skip writing files that already exist.
    """
    base_dir = base_path or "plants"
    plant_dir = os.path.join(base_dir, str(plant_id))
    # Ensure the plant directory exists
    try:
        os.makedirs(plant_dir, exist_ok=True)
    except Exception as e:
        _LOGGER.error("Failed to create directory %s: %s", plant_dir, e)
        return

    # Define default structure for storage and processing profiles
    storage_data = {
        "shelf_life": None,
        "spoilage_conditions": None,
        "packaging_type": None,
        "storage_environment": {
            "temperature": None,
            "relative_humidity": None,
            "airflow": None,
            "darkness": None
        },
        "stability_notes": None,
        "post_storage_QA": None
    }
    processing_data = {
        "postharvest_steps": None,
        "critical_control_points": None,
        "residue_breakdown": None,
        "transformation_compounds": None,
        "value_added_processing_options": None,
        "food_grade_standards": None,
        "pharmaceutical_standards": None
    }

    # File paths for the new profile files
    storage_file = os.path.join(plant_dir, "storage.json")
    processing_file = os.path.join(plant_dir, "processing.json")

    # Write or skip storage.json
    if os.path.exists(storage_file) and not overwrite:
        _LOGGER.info("storage.json already exists for plant '%s'; skipping (overwrite=False).", plant_id)
    else:
        try:
            with open(storage_file, "w", encoding="utf-8") as f:
                json.dump(storage_data, f, indent=2)
            if os.path.exists(storage_file) and overwrite:
                _LOGGER.info("Overwrote existing storage.json for plant '%s'.", plant_id)
            else:
                _LOGGER.info("Created storage.json for plant '%s'.", plant_id)
        except Exception as e:
            _LOGGER.error("Failed to write storage.json for plant '%s': %s", plant_id, e)

    # Write or skip processing.json
    if os.path.exists(processing_file) and not overwrite:
        _LOGGER.info("processing.json already exists for plant '%s'; skipping (overwrite=False).", plant_id)
    else:
        try:
            with open(processing_file, "w", encoding="utf-8") as f:
                json.dump(processing_data, f, indent=2)
            if os.path.exists(processing_file) and overwrite:
                _LOGGER.info("Overwrote existing processing.json for plant '%s'.", plant_id)
            else:
                _LOGGER.info("Created processing.json for plant '%s'.", plant_id)
        except Exception as e:
            _LOGGER.error("Failed to write processing.json for plant '%s': %s", plant_id, e)