import logging

from .profile_helpers import write_profile_sections

_LOGGER = logging.getLogger(__name__)


def initialize_recipe_vpd_logs(plant_id: str, base_path: str | None = None, overwrite: bool = False) -> bool:
    """Create recipe audit and VPD adjustment logs for ``plant_id``."""
    profile_sections = {
        "recipe_audit_log.json": [],
        "vpd_adjustment_log.json": [],
    }
    return bool(write_profile_sections(plant_id, profile_sections, base_path, overwrite))
