import logging
from .profile_helpers import write_profile_sections

_LOGGER = logging.getLogger(__name__)


def initialize_solution_logs(plant_id: str, base_path: str | None = None, overwrite: bool = False) -> bool:
    """Create pH adjustment and recipe revision logs for ``plant_id``."""
    profile_sections = {
        "ph_adjustment_log.json": [],
        "recipe_revision_log.json": [],
    }
    return bool(write_profile_sections(plant_id, profile_sections, base_path, overwrite))
