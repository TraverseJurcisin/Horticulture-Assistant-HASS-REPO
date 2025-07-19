import logging
import json
import os

_LOGGER = logging.getLogger(__name__)

def scaffold_profile_files(plant_id: str, base_path: str = None, overwrite: bool = False) -> None:
    """Create phenophase_observations.json and developmental_thresholds.json for a given plant's profile directory.

    This scaffolds a directory under the base_path (defaults to "plants") named after the plant_id,
    and creates two JSON files within it: "phenophase_observations.json" and "developmental_thresholds.json".
    Each file contains preset fields relevant to plant phenological observations and developmental thresholds, initialized to null values.
    If a file already exists and overwrite is False, the file is left unchanged.
    Set overwrite=True to replace any existing files with the default structure.
    Logs messages for each created file, any skipped creations, and any errors encountered.
    """
    base_dir = base_path or "plants"
    plant_dir = os.path.join(base_dir, str(plant_id))
    # Ensure the plant directory exists
    try:
        os.makedirs(plant_dir, exist_ok=True)
    except Exception as e:
        _LOGGER.error("Failed to create directory %s for plant profile: %s", plant_dir, e)
        return

    # Define default structures for phenophase observations and developmental thresholds
    phenophase_observations_data = {
        "bud_break_date": None,
        "flowering_onset": None,
        "fruit_set_date": None,
        "first_harvest": None,
        "senescence_onset": None,
        "recorded_by": None,
        "notes": None
    }
    developmental_thresholds_data = {
        "gdd_required_per_stage": None,
        "photoperiod_triggers": None,
        "chill_hours_required": None,
        "stage_transition_factors": None,
        "nutrient_triggers": None,
        "vgi_thresholds": None
    }

    # File paths
    phenophase_file = os.path.join(plant_dir, "phenophase_observations.json")
    thresholds_file = os.path.join(plant_dir, "developmental_thresholds.json")

    # Write or skip phenophase_observations.json
    if not overwrite and os.path.isfile(phenophase_file):
        _LOGGER.info("Phenophase observations file already exists at %s; skipping (overwrite=False).", phenophase_file)
    else:
        try:
            with open(phenophase_file, "w", encoding="utf-8") as f:
                json.dump(phenophase_observations_data, f, indent=2)
            _LOGGER.info("Phenophase observations profile created for plant %s at %s", plant_id, phenophase_file)
        except Exception as e:
            _LOGGER.error("Failed to write phenophase observations profile for plant %s: %s", plant_id, e)

    # Write or skip developmental_thresholds.json
    if not overwrite and os.path.isfile(thresholds_file):
        _LOGGER.info("Developmental thresholds file already exists at %s; skipping (overwrite=False).", thresholds_file)
    else:
        try:
            with open(thresholds_file, "w", encoding="utf-8") as f:
                json.dump(developmental_thresholds_data, f, indent=2)
            _LOGGER.info("Developmental thresholds profile created for plant %s at %s", plant_id, thresholds_file)
        except Exception as e:
            _LOGGER.error("Failed to write developmental thresholds profile for plant %s: %s", plant_id, e)