import logging

from .profile_helpers import write_profile_sections

_LOGGER = logging.getLogger(__name__)

def generate_biochemistry_profiles(plant_id: str, base_path: str = None, overwrite: bool = False) -> str:
    """
    Generate or update biochemistry and metabolite profile files for a given plant.

    This function scaffolds two JSON files (`biochemistry.json` and `metabolite_profile.json`) in the `plants/<plant_id>/` directory.
    It populates these files with predefined keys related to the plant's biochemical composition and metabolite profile,
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

    # Define default content for biochemistry.json
    biochemistry_data = {
        "flavor_aromatic_compounds": None,
        "medicinal_uses": None,
        "bioavailability": None,
        "nutrient_density": None,
        "antioxidant_load": None,
        "toxin_profiles": None
    }

    # Define default content for metabolite_profile.json
    metabolite_profile_data = {
        "cannabinoids": None,
        "alkaloids": None,
        "terpenes": None,
        "polyphenols": None,
        "enzymatic_inhibitors": None,
        "hormone_influencers": None,
        "biosynthetic_pathway_markers": None
    }

    profile_sections = {
        "biochemistry.json": biochemistry_data,
        "metabolite_profile.json": metabolite_profile_data,
    }

    return write_profile_sections(plant_id, profile_sections, base_path, overwrite)
