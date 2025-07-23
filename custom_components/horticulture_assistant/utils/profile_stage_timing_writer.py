import logging

from .profile_helpers import write_profile_sections

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
        "calendar_timing.json": calendar_timing_data,
    }

    return write_profile_sections(plant_id, profile_sections, base_path, overwrite)
