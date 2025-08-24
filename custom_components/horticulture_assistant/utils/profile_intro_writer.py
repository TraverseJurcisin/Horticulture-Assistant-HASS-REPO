import logging

from .profile_helpers import write_profile_sections

_LOGGER = logging.getLogger(__name__)


def scaffold_profile_files(
    plant_id: str, base_path: str | None = None, overwrite: bool = False
) -> str:
    """Create introduction and identification profile files for ``plant_id``."""
    profile_sections = {
        "introduction.json": {
            "primary_uses": None,
            "duration": None,
            "growth_habit": None,
            "key_features": None,
            "deciduous_or_evergreen": None,
            "history": None,
            "native_regions": None,
            "domestication": None,
            "cultural_significance": None,
            "legal_restrictions": None,
            "etymology": None,
            "cautions": None,
        },
        "identification.json": {
            "general_description": None,
            "leaf_structure": None,
            "adaptations": None,
            "rooting": None,
            "storm_resistance": None,
            "self_pruning": None,
            "growth_rates": None,
            "dimensions": None,
            "phylogeny": None,
            "defenses": None,
            "ecological_interactions": None,
        },
    }
    return write_profile_sections(plant_id, profile_sections, base_path, overwrite)
