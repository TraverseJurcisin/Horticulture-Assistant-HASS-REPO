import logging

from .profile_helpers import write_profile_sections

_LOGGER = logging.getLogger(__name__)

def generate_soil_profiles(plant_id: str, base_dir: str = None, overwrite: bool = False) -> str:
    """
    Generate or update soil and microbiome profile files for a given plant.

    This function scaffolds two JSON files (`soil_relationships.json` and `microbiome.json`)
    in the `plants/<plant_id>/` directory. It populates these files with predefined keys related
    to the plant's soil relationships and soil microbiome information, with all values defaulting to null.

    If a file already exists and `overwrite` is False, the file is left unchanged.
    If `overwrite` is True or the file is missing, a new file is created (or an existing file is overwritten) with the default structure.

    All actions (creation, skipping, overwriting) are logged for clarity.

    :param plant_id: Identifier for the plant (used as directory name under the base path).
    :param base_dir: Optional base directory path for plant profiles (defaults to "plants/" in the current working directory).
    :param overwrite: If True, overwrite existing files; if False, skip writing if files already exist.
    :return: The plant_id if profiles were successfully generated (or already present without changes),
             or an empty string on error (e.g., if directory creation fails).
    """

    # Define default content for soil_relationships.json
    soil_relationships_data = {
        "ph_range": None,
        "soil_ec_preference": None,
        "bulk_density": None,
        "cec_tolerance": None,
        "texture_class": None,
        "allelopathy": None,
        "root_soil_response": None,
        "media_suitability": None
    }

    # Define default content for microbiome.json
    microbiome_data = {
        "microbial_associations": None,
        "pathogenic_suppressors": None,
        "root_exudates": None,
        "microbial_diversity_index": None,
        "co_cultured_species": None
    }

    profile_sections = {
        "soil_relationships.json": soil_relationships_data,
        "microbiome.json": microbiome_data,
    }

    return write_profile_sections(plant_id, profile_sections, base_dir, overwrite)
