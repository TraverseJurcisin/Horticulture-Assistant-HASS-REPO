import logging

from .profile_helpers import write_profile_sections

_LOGGER = logging.getLogger(__name__)


def scaffold_profile_files(plant_id: str, base_path: str | None = None, overwrite: bool = False) -> str:
    """Create regulatory and export profile files for ``plant_id``."""
    profile_sections = {
        "regulatory.json": {
            "propagation_laws": None,
            "local_restrictions": None,
            "state_restrictions": None,
            "national_restrictions": None,
            "seed_labeling_requirements": None,
            "intellectual_property_claims": None,
            "banned_substances": None,
            "ethical_sourcing": None,
        },
        "export_profile.json": {
            "exportable_forms": None,
            "phytosanitary_certificates": None,
            "fumigation_status": None,
            "customs_codes": None,
            "known_trade_restrictions": None,
            "preferred_international_markets": None,
            "country_specific_demand": None,
        },
    }
    return write_profile_sections(plant_id, profile_sections, base_path, overwrite)
