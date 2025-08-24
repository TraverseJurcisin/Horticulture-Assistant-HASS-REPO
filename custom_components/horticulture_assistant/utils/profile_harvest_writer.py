import logging

from .profile_helpers import write_profile_sections

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

    # Define default content for harvest.json
    harvest_data = {
        "harvest_timing": None,
        "indicators_of_ripeness": None,
        "harvesting_method": None,
        "postharvest_storage": None,
        "spoilage_rate": None,
        "market_channels": None,
    }

    # Define default content for yield.json
    yield_data = {
        "expected_yield_range": None,
        "standard_yield_unit": None,
        "per_area_volume_metrics": {
            "per_acre": None,
            "per_cubic_ft": None,
            "per_gallon_media": None,
        },
        "historical_yield": None,
        "yield_density_range": None,
        "projected_yield_model": None,
    }

    profile_sections = {
        "harvest.json": harvest_data,
        "yield.json": yield_data,
    }

    return write_profile_sections(plant_id, profile_sections, base_dir, overwrite)
