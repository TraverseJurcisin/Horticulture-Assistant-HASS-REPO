import logging

from .profile_helpers import write_profile_sections

_LOGGER = logging.getLogger(__name__)


def generate_profile_logs(plant_id: str, base_path: str | None = None, overwrite: bool = False) -> str:
    """Create pest scouting and irrigation log files for ``plant_id``."""
    profile_sections = {
        "pest_scouting_log.json": [],
        "irrigation_log.json": [],
    }
    return write_profile_sections(plant_id, profile_sections, base_path, overwrite)
