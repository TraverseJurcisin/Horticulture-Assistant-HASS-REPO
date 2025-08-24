import logging

from .profile_helpers import write_profile_sections

_LOGGER = logging.getLogger(__name__)


def scaffold_profile_files(
    plant_id: str, base_path: str | None = None, overwrite: bool = False
) -> str:
    """Create environmental incident and cultural disruption logs for ``plant_id``."""
    profile_sections = {
        "environmental_incident_log.json": [],
        "cultural_disruption_log.json": [],
    }
    return write_profile_sections(plant_id, profile_sections, base_path, overwrite)
