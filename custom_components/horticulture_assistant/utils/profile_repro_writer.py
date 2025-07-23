import logging

from .profile_helpers import write_profile_sections

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
        "phenology.json": phenology_data,
    }

    return write_profile_sections(plant_id, profile_sections, base_dir, overwrite)
